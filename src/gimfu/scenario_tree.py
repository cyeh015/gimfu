from t2data import t2data
from mulgrids import mulgrid

from gimfu.scenario_spec_report import collate_well_stacks
from gimfu.scenario_extraction import external_name
from gimfu.scenario_extraction import ScenarioDir
from gimfu.basic_units import (
    to_kjkg,
    to_bar,
    to_year,
    to_tday,
    to_tday_rev,
)

from pathlib import Path
import json
import glob
import shutil
import os
from pprint import pprint



class StationGenerGroup():
    def __init__(self, tmak_name='tmk', check_name='chk'):
        self.tmak_found = False
        self.reset_found = False
        self.prd_geners = []
        self.inj_geners = []
        self.chk_geners = []
        self.tmak_gener = None

        self._tmak_name = tmak_name
        self._check_name = check_name

    def add_gener(self, g):
        if g.name.startswith(self._tmak_name) and g.type == 'TMAK':
            if self.tmak_found:
                raise Exception('Multiple TMAK found in group: ', self.tmak_gener, g)
            self.tmak_gener = g
            self.tmak_found = True
        elif g.name.startswith(self._check_name) and g.type == 'FINJ':
            self.chk_geners.append(g)
            if float(g.fg) != 0.0:
                self.reset_found = True
        else:
            if self.reset_found:
                raise Exception('Generator added after reset check found: ', g)
            if self.tmak_found:
                self.inj_geners.append(g)
            else:
                self.prd_geners.append(g)

    def parse_TMAK(self, gener):
        if gener.type != 'TMAK':
            raise Exception
        scaling = None
        if gener.hg < 0.0:
            scaling = 'uniform'
            if gener.hg < -1.0:
                scaling = 'progressive'
        return {
            'mass_target_tday': to_tday(gener.gx),
            'steam_target_tday': to_tday(gener.ex),
            'scaling': scaling,
        }

    def is_valid(self):
        return self.tmak_found and self.reset_found

    def dump(self):
        grp = {
            'prd_geners': [ [g.block, g.name] for g in self.prd_geners ],
            'inj_geners': [ [g.block, g.name] for g in self.inj_geners ],
            'chk_geners': [ [g.block, g.name] for g in self.chk_geners ],
        }
        if self.tmak_gener is not None:
            grp.update(self.parse_TMAK(self.tmak_gener))
            grp['name'] = str(self.tmak_gener)
        return grp

    def __repr__(self):
        return f"StationGenerGroup(" \
               f"tmak_found={self.tmak_found}, " \
               f"reset_found={self.reset_found}, " \
               f"prd_geners={len(self.prd_geners)}, " \
               f"inj_geners={len(self.inj_geners)}, " \
               f"chk_geners={len(self.chk_geners)})"

def get_gener_wellname_stackname(g, well_stack_specs, alias={}, grouping={}):
    """ return (well_name, stack_name)

    g [block_name, gener_name]
    well_stack_spec is from collate_well_stacks() based on scenario_spec.json
    alias is a backup dict converting gener name to prettier looking "well_name"
    """
    for stack_name, stack in well_stack_specs.items():
        for well_name, ggs in stack['geners'].items():
            for gg in ggs:
                if gg == g:
                    return well_name, stack_name
    # backup: use alias and custom grouping
    well_name = alias.get(g[1], '')
    group_name = ''
    for grp, gnames in grouping.items():
        if well_name in gnames or g[1] in gnames:
            group_name = grp
    # if all failed: '', ''
    return well_name, group_name

def scenario_tree(sdir, scenario_name, gener_alias={}, custom_grouping={}, geo=None):
    scenario = ScenarioDir(sdir)
    dat_fnames = scenario.dat_filenames
    offset_yr = scenario.specification["date_offset"]
    sims = scenario.specification['simulations']

    dats = []
    print('found .dat files:')
    for fdat in dat_fnames:
        print(f'    loading {fdat} ...')
        dats.append(t2data(fdat))

    output_data = []
    for dat, sim in zip(dats, sims):
        start_yr = to_year(sim['aut2_tstart_sec'], offset_yr)
        end_yr = to_year(sim['aut2_tstop_sec'], offset_yr)
        print(f'    Scenario {sim["filename"]}:  {start_yr} -> {end_yr}')

        groups = []
        grp = StationGenerGroup()
        for g in dat.generatorlist:
            if grp.reset_found:
                grp = StationGenerGroup()
            grp.add_gener(g)
            if grp.is_valid():
                # print(f"    {grp}")
                grp_data = grp.dump()
                # use gener_alias for friendly station group name
                grp_data['name'] = gener_alias.get(grp.tmak_gener.name, grp_data['name'])
                groups.append(grp_data)

        well_stack_specs, _ = collate_well_stacks(scenario.specification)

        for grp_data in groups:
            for g_type in ['prd', 'inj']:
                gs, wells, stacks = [], [], []
                for g in grp_data[g_type + '_geners']:
                    well_name, stack_name = get_gener_wellname_stackname(
                        g,
                        well_stack_specs,
                        gener_alias,
                        custom_grouping,
                        )
                    g_data = {
                        'block': g[0],
                        'name': g[1],
                        'well': well_name,
                        'stack': stack_name,
                    }
                    if geo is not None:
                        g_data.update({
                            'elevation': geo.block_centre(
                                geo.layer_name(g[0]), geo.column_name(g[0]))[2],
                        })
                    # --------------
                    gs.append(g_data)
                    if well_name not in wells:
                        if well_name:
                            wells.append(well_name)
                    if stack_name not in stacks:
                        if stack_name:
                            stacks.append(stack_name)
                    # --------------
                grp_data.update({
                    g_type + '_geners': gs,
                    g_type + '_wells': wells,
                    g_type + '_stacks': stacks,
                })

        output_data.append({
            'simulation': sim["filename"],
            'start_year': start_yr,
            'end_year': end_yr,
            'station_groups': groups,
            })

    output_filename = f"meta_geners_{scenario_name}.json"
    with open(output_filename, 'w') as f:
        json.dump(output_data, f, indent=4)



def extract_meta():
    with open('settings.json', 'r') as f:
        cfg = json.load(f)

    gener_alias = cfg.get('gener_alias', {})
    custom_grouping = cfg.get('custom_grouping', {})
    geo = mulgrid(cfg['geometry'])

    for sdir in cfg['dir_to_extract']:
        # use basename (the last part of the the normalized path) as sname
        sname = os.path.basename(os.path.normpath(sdir))
        sname = external_name(cfg, sname)
        print("\nExtracting scenario '%s' from directory: %s" % (sname, sdir))

        scenario_tree(sdir, sname, gener_alias, custom_grouping, geo)

def extract_raw_spec():
    """ copy the spec json from sdir """
    with open('settings.json', 'r') as f:
        cfg = json.load(f)

    for sdir in cfg['dir_to_extract']:
        # use basename (the last part of the the normalized path) as sname
        sname = os.path.basename(os.path.normpath(sdir))
        sname = external_name(cfg, sname)
        print("\nExtracting scenario '%s' from directory: %s" % (sname, sdir))

        spec_file = Path(sdir) / Path('scenario_spec.json')
        shutil.copy(str(spec_file), f'meta_spec_{sname}.json')


if __name__ == '__main__':
    extract_meta()
