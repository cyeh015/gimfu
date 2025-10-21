import re
import numpy as np

def get_block_history(bname, lsts, cols=None):
    """ return history tables keyed by block name
    bname can be either a list, or a regular expression string
    """
    if cols is None:
        cols = ['Pressure']
    if not isinstance(lsts,list):
        lsts = [lsts]
    if isinstance(bname, list):
        # change list og block names into regular expression
        bname = '(' + '|'.join(bname) + ')'

    full_table = {}
    full_bcns = []
    for lst in lsts:
        print('in listing file %s:' % lst.filename)
        # create zeros for each matching (b,g,cn) in current listing
        bis, bs = [], [] # indices in gener and element tables
        blk_hist, blk_time, collated_bs = {}, {}, [] # collate potential multiple (b,g)s into a single one
        for i,b in enumerate(lst.element.row_name):
            if re.match(re.compile(bname), b):
                bis.append(i)
                bs.append(b)
                for cn in cols:
                    if (b,cn) not in blk_hist:
                        collated_bs.append((b,cn))
                        blk_hist[(b,cn)] = np.zeros_like(lst.fulltimes)
                        blk_time[(b,cn)] = np.copy(lst.fulltimes)
        # sum through tables in current listing
        for j,t in enumerate(lst.fulltimes):
            lst.index = j
            for cn in cols:
                for i,b in zip(bis, bs):
                    blk_hist[(b,cn)][j] = blk_hist[(b,cn)][j] + lst.element[cn][i]
        for k in collated_bs:
            if k not in full_table:
                print('    (new) found matching block %s' % str(k))
                full_bcns.append(k)
                full_table[k] = (blk_time[k], blk_hist[k])
            else:
                print('          found matching block %s' % str(k))
                full_table[k] = (np.concatenate((full_table[k][0], blk_time[k])),
                                 np.concatenate((full_table[k][1], blk_hist[k])))
    return full_table, full_bcns


def get_gener_history(bname, gname, lsts, cols=None, silent=True):
    """ return history tables keyed by (block name, gener name, column name)
    bname and gname are strings that support regular expression.

    If bname and gname are simple strings, they are used as as regular
    expression to match any geners that match them.  A tuple of (full_table,
    full_bgcns) is returned.  full_bgcns is a list of (blockname, genername,
    columnname).  Full table is a dict using the (b, g, cn) as key.  Each item
    is a tuple of times and values.

    If bname and gname are supplied as two lists (needs to match length),
    full_bgcns will be a list of tuple that is identical to zip(bname, gname).
    Any of these entries will have zero values filled with the same length as
    lst.fulltimes.

    Values of repeated (b,g) generators are summed together.  Enthalpy is
    averaged by generation rate.  If the gener has flowrate of zero, it will use
    the enthalpy value from the listing table.  Usually AUT2 (DMAK/DMAT etc)
    calculate the enthalpy value anyway even if not flowing at the time.

    Internally it always sums up Generation rate and averages Enthalpy, even if
    they are absent from user specified cols.  This greatly simplifies the
    unique averaging enthalpy, which is often required anyway.
    """
    if not isinstance(lsts,list):
        lsts = [lsts]

    if isinstance(bname, list) and isinstance(gname, list) and len(bname) == len(gname):
        # pad zeros even if (b,g) not exist in current listing
        add_bgs = list(zip(bname,gname))
    else:
        # if bname and gname are strings, assume regular expression
        add_bgs = []
        rebn, regn = re.compile(bname), re.compile(gname)

    rate_cname, stm_cname, enth_cname = None, None, None
    for cn in lsts[0].generation.column_name:
        if cn.lower().startswith('generation ra'):
            rate_cname = cn
        if cn.lower().startswith('steam sep'):
            stm_cname = cn
        if cn.lower().startswith('enthal'):
            enth_cname = cn
    if cols is None:
        cols = [rate_cname]

    full_table = {}
    full_bgcns = []
    for lst in lsts:
        if not silent:
            print('in listing file %s:' % lst.filename)
        # create zeros for each matching (b,g,cn) in current listing
        gen_hist, gen_time = {}, {} # used interally
        collated_bgcns = [] # collate potential multiple (b,g)s into a single one

        # have value zeros even if specified (b,g) not in current t2listing
        for b,g in add_bgs:
            for cn in cols:
                if (b,g,cn) not in gen_hist:
                    collated_bgcns.append((b,g,cn))
                    gen_hist[(b,g,cn)] = np.zeros_like(lst.fulltimes)
                    gen_time[(b,g,cn)] = np.copy(lst.fulltimes)
            if (b,g,rate_cname) not in gen_hist:
                gen_hist[(b,g,rate_cname)] = np.zeros_like(lst.fulltimes)
            if (b,g,enth_cname) not in gen_hist:
                gen_hist[(b,g,enth_cname)] = np.zeros_like(lst.fulltimes)
        # actually exists in current t2listing
        gis, bgs = [], [] # indices in gener table
        for i,(b,g) in enumerate(lst.generation.row_name):
            found = False
            if add_bgs:
                # if one of specified list
                if (b,g) in add_bgs:
                    found = True
            else:
                if re.match(rebn, b) and re.match(regn, g):
                    found = True
            if found:
                gis.append(i)
                bgs.append((b,g))
                for cn in cols:
                    if (b,g,cn) not in gen_hist:
                        collated_bgcns.append((b,g,cn))
                        gen_hist[(b,g,cn)] = np.zeros_like(lst.fulltimes)
                        gen_time[(b,g,cn)] = np.copy(lst.fulltimes)
                if (b,g,rate_cname) not in gen_hist:
                    gen_hist[(b,g,rate_cname)] = np.zeros_like(lst.fulltimes)
                if (b,g,enth_cname) not in gen_hist:
                    gen_hist[(b,g,enth_cname)] = np.zeros_like(lst.fulltimes)
        # sum/average through tables in current listing
        for j,t in enumerate(lst.fulltimes):
            lst.index = j
            for i,(b,g) in zip(gis, bgs):
                # do massflow and average enthalpy separately
                total_heat = gen_hist[(b,g,rate_cname)][j] * gen_hist[(b,g,enth_cname)][j]
                total_heat += lst.generation[rate_cname][i] * lst.generation[enth_cname][i]
                total_mass = gen_hist[(b,g,rate_cname)][j] + lst.generation[rate_cname][i]
                if abs(total_mass) < 1.0e-10:
                    # avg_enth = 0.0
                    avg_enth = lst.generation[enth_cname][i]
                else:
                    avg_enth = total_heat / total_mass
                gen_hist[(b,g,enth_cname)][j] = avg_enth
                gen_hist[(b,g,rate_cname)][j] = total_mass
                for cn in cols:
                    if cn in [rate_cname, enth_cname]:
                        # already done separately above
                        pass
                    else:
                        # simply add everything else
                        gen_hist[(b,g,cn)][j] = gen_hist[(b,g,cn)][j] + lst.generation[cn][i]
        for k in collated_bgcns:
            # k is (block name, gener name, column name)
            if k not in full_table:
                if not silent:
                    print('    (new) found matching gener %s' % str(k))
                full_bgcns.append(k)
                full_table[k] = (gen_time[k], gen_hist[k])
            else:
                if not silent:
                    print('          found matching gener %s' % str(k))
                full_table[k] = (np.concatenate((full_table[k][0], gen_time[k])),
                                 np.concatenate((full_table[k][1], gen_hist[k])))
    return full_table, full_bgcns

def get_gener_history_v0(bname, gname, lsts, cols=None):
    """ return history tables keyed by (block name, gener name, column name)
    bname and gname are strings that support regular expression

    Values of repeated (b,g) generators are summed together.  Hence column
    name such as Enthalpy won't work properly
    """
    if cols is None:
        cols = ['Generation rate']
    if not isinstance(lsts,list):
        lsts = [lsts]

    full_table = {}
    full_bgcns = []
    for lst in lsts:
        print('in listing file %s:' % lst.filename)
        # create zeros for each matching (b,g,cn) in current listing
        gis, bgs = [], [] # indices in gener and element tables
        gen_hist, gen_time, collated_bgcns = {}, {}, [] # collate potential multiple (b,g)s into a single one
        for i,(b,g) in enumerate(lst.generation.row_name):
            if re.match(re.compile(bname), b) and re.match(re.compile(gname), g):
                gis.append(i)
                bgs.append((b,g))
                for cn in cols:
                    if (b,g,cn) not in gen_hist:
                        collated_bgcns.append((b,g,cn))
                        gen_hist[(b,g,cn)] = np.zeros_like(lst.fulltimes)
                        gen_time[(b,g,cn)] = np.copy(lst.fulltimes)
        # sum through tables in current listing
        for j,t in enumerate(lst.fulltimes):
            lst.index = j
            for cn in cols:
                for i,(b,g) in zip(gis, bgs):
                    gen_hist[(b,g,cn)][j] = gen_hist[(b,g,cn)][j] + lst.generation[cn][i]
        for k in collated_bgcns:
            if k not in full_table:
                print('    (new) found matching gener %s' % str(k))
                full_bgcns.append(k)
                full_table[k] = (gen_time[k], gen_hist[k])
            else:
                print('          found matching gener %s' % str(k))
                full_table[k] = (np.concatenate((full_table[k][0], gen_time[k])),
                                 np.concatenate((full_table[k][1], gen_hist[k])))
    return full_table, full_bgcns
