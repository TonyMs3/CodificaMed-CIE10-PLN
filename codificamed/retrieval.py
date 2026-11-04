"""Recuperación supervisada con evidencias de TRAIN, sin consultar DEV/TEST."""
import csv,re,unicodedata
from collections import defaultdict
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import linear_kernel
from .data import DATA,documents,normalize
VERSION='2.0'
DEFAULT_K=40

def lexical(text):
    text=''.join(c for c in unicodedata.normalize('NFD',text.lower()) if unicodedata.category(c)!='Mn')
    return ' '.join(re.findall(r'[a-z0-9]+',text))

def fragments(note):
    return [part.strip() for part in re.split(r'(?<=[.!?;])\s+|\n+',note) if part.strip()]

def training_phrases(catalog):
    paths=list((DATA/'corpus').rglob('trainX.tsv'))
    if len(paths)!=1: raise ValueError('Falta trainX.tsv: ejecuta python -m scripts.prepare')
    labels={row['id']:set(row['gold']) for row in documents('train')}
    pairs=set()
    with paths[0].open(encoding='utf-8-sig',newline='') as stream:
        for row in csv.reader(stream,delimiter='\t'):
            if len(row)!=5: raise ValueError('CodiEsp-X debe tener 5 columnas')
            doc_id,label,code,phrase,_=row;code=normalize(code)
            if label!='DIAGNOSTICO': continue
            if doc_id not in labels or code not in labels[doc_id]: raise ValueError('Anotación X incompatible con train D')
            if code in catalog and 3<=len(phrase.strip())<=160: pairs.add((code,phrase.strip()))
    return sorted(pairs)

class Retriever:
    def __init__(self,catalog,use_train=None):
        self.catalog=catalog;self.codes=sorted(catalog);self.code_index={c:i for i,c in enumerate(self.codes)}
        use_train=len(catalog)>10000 if use_train is None else use_train
        pairs=training_phrases(catalog) if use_train else []
        resources=[(c,catalog[c]) for c in self.codes]+pairs
        self.training_pairs=len(pairs)
        self.resource_codes=np.array([self.code_index[c] for c,_ in resources])
        texts=[text for _,text in resources]
        self.vectorizer=TfidfVectorizer(analyzer='char_wb',ngram_range=(3,5),strip_accents='unicode',dtype=np.float32,max_features=60000)
        self.word_vectorizer=TfidfVectorizer(ngram_range=(1,2),strip_accents='unicode',dtype=np.float32,max_features=60000)
        self.matrix=self.vectorizer.fit_transform(texts)
        self.word_matrix=self.word_vectorizer.fit_transform(texts)
        self.exact=defaultdict(set)
        for code,text in resources:
            phrase=lexical(text)
            if 3<=len(phrase)<=120 and len(phrase.split())<=12: self.exact[phrase].add(self.code_index[code])
    def retrieve(self,note,k=DEFAULT_K):
        text=re.sub(r'\bHTA\b','hipertensión esencial',note,flags=re.I)
        text=re.sub(r'\bDM2\b','diabetes mellitus tipo 2',text,flags=re.I)
        text=re.sub(r'\bneumonía no especificada\b','neumonía microorganismo no especificado',text,flags=re.I)
        parts=fragments(text)
        if not parts: return {}
        similarities=.35*linear_kernel(self.vectorizer.transform(parts),self.matrix)+.65*linear_kernel(self.word_vectorizer.transform(parts),self.word_matrix)
        scores=np.zeros((len(parts),len(self.codes)),dtype=np.float32)
        np.maximum.at(scores.T,self.resource_codes,similarities.T)
        # Coincidencias literales de descripciones y variantes anotadas exclusivamente en TRAIN.
        for row,part in enumerate(parts):
            words=lexical(part).split()
            for start in range(len(words)):
                for size in range(1,min(12,len(words)-start)+1):
                    phrase=' '.join(words[start:start+size])
                    for index in self.exact.get(phrase,()):
                        scores[row,index]=max(scores[row,index],1+min(size,8)*.025)
        best=scores.max(axis=0)
        # Primero coincidencias exactas, después diversidad por fragmento y ranking global.
        selected=[int(i) for i in np.argsort(-best,kind='stable') if best[i]>=1][:k]
        ranked=np.argsort(-scores,axis=1,kind='stable')
        for rank in range(min(2,len(self.codes))):
            for row in range(len(parts)):
                index=int(ranked[row,rank])
                if scores[row,index]>0 and index not in selected and len(selected)<k: selected.append(index)
        for index in np.argsort(-best,kind='stable'):
            if len(selected)>=k: break
            if best[index]>0 and index not in selected: selected.append(int(index))
        return {self.codes[i]:self.catalog[self.codes[i]] for i in selected}
