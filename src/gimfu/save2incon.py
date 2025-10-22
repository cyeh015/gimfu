""" use: save2incon a.save b.incon [-reset_kcyc] """

from sys import *
from t2incons import *

def main():
    if len(argv) < 2:
        print('use: save2incon a.save b.incon [-reset_kcyc]')
        exit(1)

    readFrom = argv[1]
    saveTo = argv[2]

    if len(argv) > 3:
        opt = argv[3]
    else:
        opt = ''
    inc = t2incon(readFrom)

    if opt == '-reset_kcyc':
        inc.timing['kcyc'] = 1
        inc.timing['iter'] = 1

    inc.write(saveTo)

if __name__ == '__main__':
    main()
