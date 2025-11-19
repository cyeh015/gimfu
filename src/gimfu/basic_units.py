def to_kjkg(xs):
    try:
        return [x/1000. for x in xs]
    except TypeError:
        return xs/1000.

def to_bar(xs):
    try:
        return [x/1.e5 for x in xs]
    except TypeError:
        return xs/1.e5

def to_year(xs,start_year=0.0):
    sec_in_year = 60. * 60. * 24. * 365.25
    try:
        return [x / sec_in_year + start_year for x in xs]
    except TypeError:
        return xs / sec_in_year + start_year

def to_tday(xs):
    try:
        return [x * 86.4 for x in xs]
    except TypeError:
        return xs * 86.4

def to_tday_rev(xs):
    try:
        return [-x * 86.4 for x in xs]
    except TypeError:
        return -xs * 86.4
