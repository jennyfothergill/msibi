import os

import gsd
import gsd.hoomd
import mdtraj as md


HOOMD2_HEADER = """
import hoomd
import hoomd.md
from hoomd.init import read_gsd

hoomd.context.initialize("")
try:
    system = read_gsd("{0}", frame=-1, time_step=0)
except RuntimeError:
    from hoomd.deprecated.init import read_xml
    system = read_xml(filename="{0}", wrap_coordinates=True)
T_final = {1:.1f}

pot_width = {2:d}
nl = hoomd.md.nlist.cell()
table = hoomd.md.pair.table(width=pot_width, nlist=nl)

"""

HOOMD_TABLE_ENTRY = """
table.set_from_file('{type1}', '{type2}', filename='{potential_file}')
"""


class State(object):
    """A single state used as part of a multistate optimization.

    Attributes
    ----------
    kT : float
        Unitless heat energy (product of Boltzmann's constant and temperature).
    state_dir : path
        Path to state directory (default '')
    traj_file : path or md.Trajectory
        The dcd or gsd trajectory associated with this state
        (default 'query.dcd')
    top_file : path
        hoomdxml containing topology information (needed for dcd)
        (default None)
    name : str
        State name. If no name is given, state will be named 'state-{kT:.3f}'
        (default None)
    backup_trajectory : bool
        True if each query trajectory is backed up (default False)

    """

    def __init__(
        self,
        kT,
        state_dir="",
        traj_file=None,
        top_file=None,
        name=None,
        backup_trajectory=False,
    ):
        self.kT = kT
        self.state_dir = state_dir

        self.traj_path = os.path.join(state_dir, traj_file)
        self.traj_file = traj_file

        try:
            with gsd.hoomd.open(self.traj_path) as t:
                self._is_gsd = isinstance(t, gsd.hoomd.HOOMDTrajectory)
        except RuntimeError:
            self._is_gsd = False

        if top_file:
            self.top_path = os.path.join(state_dir, top_file)
        else:
            self.top_path = None

        self.traj = None
        if not name:
            name = "state-{0:.3f}".format(self.kT)
        self.name = name

        self.backup_trajectory = backup_trajectory

    def reload_query_trajectory(self):
        """Reload the query trajectory. """
        if self.top_path:
            self.traj = md.load(self.traj_path, top=self.top_path)
        else:
            self.traj = md.load(self.traj_path)

    def save_runscript(
        self,
        table_potentials,
        table_width,
        engine="hoomd",
        runscript="hoomd_run_template.py",
    ):
        """Save the input script for the MD engine. """

        header = list()

        HOOMD_HEADER = HOOMD2_HEADER

        if self._is_gsd:
            header.append(
                    HOOMD_HEADER.format(self.traj_file, self.kT, table_width)
                    )
        else:
            header.append(
                    HOOMD_HEADER.format(self.top_path, self.kT, table_width)
                    )
        for type1, type2, potential_file in table_potentials:
            header.append(HOOMD_TABLE_ENTRY.format(**locals()))
        header = "".join(header)
        with open(os.path.join(self.state_dir, runscript)) as fh:
            body = "".join(fh.readlines())

        runscript_file = os.path.join(self.state_dir, "run.py")
        with open(runscript_file, "w") as fh:
            fh.write(header)
            fh.write(body)
