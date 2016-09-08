from __future__ import print_function
import os

class TempFileWriter(object):
    def __init__(self, fname, tmp_ext='__tmp'):
        self.fname = fname
        self.tmpname = fname+tmp_ext

    def __enter__(self):
        self.f = open(self.tmpname, 'w', os.O_TRUNC)
        return self

    def __exit__(self, type, value, traceback):
        self.f.close()
        os.rename(self.tmpname, self.fname)

    def write(self, txt):
        print(txt.encode('utf8'), file=self.f)
