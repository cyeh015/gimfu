""" shared functions that deals with extracting scenario results
"""

def external_name(cfg, sname):
    if isinstance(cfg, str):
        with open(cfg, 'r') as f:
            import json
            cfg = json.load(f)
    ext_names = cfg['external_scenario_names']
    if '-' in sname:
        parts = sname.split('-')
        new_parts = []
        for s in parts:
            try:
                s = ext_names[s]
            except KeyError:
                pass
            new_parts.append(s)
        return '-'.join(new_parts)
    else:
        return ext_names[sname]


def matching_geners_from_lsts(lsts, block_name, gener_name):
    """ return a list of (block, gener) that match the block_name and gener_name
    """
    import re
    rebn, regn = block_name, gener_name
    if isinstance(block_name, str):
         rebn = re.compile(block_name)
    if isinstance(gener_name, str):
         regn = re.compile(gener_name)
    bns_gns = []
    for lst in lsts:
        for b,g in lst.generation.row_name:
            if re.match(rebn, b) and re.match(regn, g):
                if (b, g) not in bns_gns:
                    bns_gns.append((b, g))
    return bns_gns


def average_enthalpy(massrates, enthalpies):
    """ returns total massrates and the averaged enthalpies

    massrates should be a list of numpy arrays, enthalpies should be a list of
    numpy arrays

    (lengths of the lists should be the same, length/shape of all numpy arrays
    should be the same)
    """
    import numpy as np
    totalheat = np.zeros_like(massrates[0])
    totalmass = np.zeros_like(massrates[0])
    for mass,enth in zip(massrates, enthalpies):
        totalmass += mass
        totalheat += mass * enth
    avgenths = np.divide(totalheat, totalmass, out=np.zeros_like(totalheat),
                         where=totalmass!=0)
    return totalmass, avgenths


def to_year(xs, start_year=0.0):
    sec_in_year = 60. * 60. * 24. * 365.25
    return xs / sec_in_year + start_year, 'Year'

def to_kjkg(xs):
    return xs/1000., 'kJ/kg'

def to_bar(xs):
    return xs/1.e5, 'bar'

def to_thr(xs):
    return xs * 3.6, 't/hr'

def to_thr_rev(xs):
    return xs * -3.6, 't/hr'

def to_ktd(xs):
    return xs * 0.0864, 'ktd'

def to_ktd_rev(xs):
    return xs * -0.0864, 'ktd'

def assign_kgs(xs):
    """ no convert """
    return xs, 'kg/s'

def assign_jkg(xs):
    """ no convert """
    return xs, 'J/kg'

def assign_sec(xs):
    """ no convert """
    return xs, 'sec'

