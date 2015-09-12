import colorsys
import datetime

class ColourScheme(object):
    cols_android = {
        'light_blue'   : '33b5e5',
        'blue'         : '0099cc',
        'light_purple' : 'aa66cc',
        'purple'       : '9933cc',
        'light_green'  : '99cc00',
        'green'        : '669900',
        'light_yellow' : 'ffbb33',
        'yellow'       : 'ff8800',
        'light_red'    : 'ff4444',
        'red'          : 'cc0000'}
    cols_solarized = {
        #'brblack'   : '1c1c1c',
        'black'     : '262626',
        #'brgreen'   : '585858',
        'bryellow'  : '626262',
        #'brblue'    : '808080',
        #'brcyan'    : '8a8a8a',
        #'white'     : 'e4e4e4',
        'brwhite'   : 'ffffd7',
        'yellow'    : 'af8700',
        'brred'     : 'd75f00',
        'red'       : 'd70000',
        'magenta'   : 'af005f',
        'brmagenta' : '5f5faf',
        'blue'      : '0087ff',
        'cyan'      : '00afaf',
        'green'     : '5f8700'}

    def __init__(self, seed=None):
        self.colours = {}
        self.colours.update(self.cols_android)
        self.colours.update(self.cols_solarized)
        if seed:
            self.seed = seed
        else:
            self.seed = datetime.date.today().day

    def get_colour_exp(self, key):
        h = (abs(hash(key)) % 1024)/1024.0
        (r,g,b) = colorsys.hsv_to_rgb(h, 1.0, 1.0)
        return 'rgb({0},{1},{2})'.format(int(r*255), int(g*255), int(b*255))

    def get_colour(self, key):
        h = (abs(hash(key))+self.seed) % len(self.colours)
        return self.colours[self.colours.keys()[h]]
