
import csv

from mulgrids import well

class WellPlan:
    """
    Loads and parses a planned well file exported from Seequent's Leapfrog.
    The file is expected to have two sections:
    1. A key-value header section.
    2. A tabular data section for the well track.
    The sections are separated by two empty lines.
    """
    def __init__(self, filename):
        """
        Initializes and loads the well data from the specified file.

        Args:
            filename: The path to the .csv file.
        """
        self.filename = filename
        self.header = {}
        self.data = {}
        self._load_file()

    def _load_file(self):
        """
        Internal method to handle the file parsing logic.
        """
        with open(self.filename, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        # Find the index of the separator (two consecutive '""' lines)
        separator_index = -1
        for i, line in enumerate(lines):
            if line.strip() == '""':
                if i + 1 < len(lines) and lines[i+1].strip() == '""':
                    separator_index = i
                    break
        
        if separator_index == -1:
            raise ValueError(f"Could not find the '""' separator in file: {self.filename}")

        header_lines = lines[:separator_index]
        data_lines = lines[separator_index + 2:]

        # --- Parse Header Section ---
        for line in header_lines:
            line = line.strip()
            if not line:
                continue
            
            parts = line.split(',', 1)
            if len(parts) == 2:
                key, value = parts
                # Attempt to convert numerical values to float
                try:
                    self.header[key] = float(value)
                except ValueError:
                    # Handle special case for Location coordinates
                    if key == 'Location':
                        self.header[key] = [float(coord) for coord in value.split(',')]
                    else:
                        self.header[key] = value

        # --- Parse Data Section ---
        if not data_lines:
            return

        # Use the csv module to handle potential quoting in headers or data
        reader = csv.reader(data_lines)
        
        try:
            column_headers = next(reader)
        except StopIteration:
            return # No data rows found

        self.data = {header: [] for header in column_headers}
        
        for row in reader:
            if not row: # Skip empty lines
                continue
            for i, value in enumerate(row):
                if i < len(column_headers):
                    header = column_headers[i]
                    try:
                        # Convert all data values to float
                        self.data[header].append(float(value))
                    except (ValueError, IndexError):
                        # If conversion fails or row is malformed, append as is
                        self.data[header].append(value)


    def __repr__(self):
        well_id = self.header.get('Well ID', 'N/A')
        return f"PlannedWell(filename='{self.filename}', well_id='{well_id}')"


    def block_at_layer(self, geo, layer, cache_qtree=True):
        """ return the feed block for the planned well at the specified layer

        TODO instead of simple approach of pos at the layer centre, should
             consider well curverture and trace through the layer thickness
             see:
                 https://github.com/pro-well-plan/well_profile
        """
        # get cached qtree if already generated
        geo_qtree = None
        if cache_qtree:
            if not hasattr(geo, '_qtree'):
                geo._qtree = geo.column_quadtree()
            geo_qtree = geo._qtree
        # use mulgrid/well to handle the position and block lookup
        data_columns = ['Easting', 'Northing', 'Elevation']
        pos = list(zip(*[self.data[c] for c in data_columns]))
        well_name = ''
        geo_well = well(well_name, pos)
        feed_pos = geo_well.elevation_pos(geo.layer[layer].centre)
        feed_block = geo.block_name_containing_point(feed_pos, qtree=geo_qtree)
        return feed_block

    def add_to_mulgrid(self, geo, name=None):
        """ add a well object into mulgrid """
        data_columns = ['Easting', 'Northing', 'Elevation']
        pos = list(zip(*[self.data[c] for c in data_columns]))
        if name is None:
            # default anme uses Well ID, trim to last 5 characters
            well_name = self.header.get('Well ID', 'WELL1')[-5:]
        else:
            well_name = name
        w = well(well_name, pos)
        geo.add_well(w)



