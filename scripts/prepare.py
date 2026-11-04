from codificamed.data import acquire, catalog, documents
if __name__ == '__main__':
    acquire()
    print('Catálogo:',len(catalog()))
    for split in ['train','dev','test']:
        print(split,len(documents(split)))
