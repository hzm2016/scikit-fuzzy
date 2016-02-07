"""
fuzzyvariable.py : Contains base fuzzy variable class.
"""
import numpy as np
import matplotlib.pyplot as plt

from skfuzzy import defuzz, interp_membership
from ..membership import trimf

try:
    from collections import OrderedDict
except ImportError:
    from .ordereddict import OrderedDict


class FuzzyVariableAdjective(object):
    """
    An adjective and associated member function for a fuzzy varaible.
    For example, if one were creating a FuzzyVariable with a simple three-point
    liker scale, three `FuzzyVariableAdjective` would be created: poor, average,
    and good.
    """

    def __init__(self, label, membership_function):
        self.label = label
        self.mf = membership_function

        self.parent_variable = None
        self.membership_value = None

    @property
    def not_(self):
        """
        Complement of this adjective.

        Returns
        -------
        not self
        """
        lbl = "NOT-" + self.label
        result = FuzzyVariableAdjective(lbl, 1. - self.mf)
        if self.membership_value is not None:
            result.membership_value = 1. - self.membership_value
        self.parent_variable[lbl] = result
        return result

    @property
    def full_label(self):
        """Adjective with parent.  Ex: velocity['fast']"""
        if self.parent_variable is None:
            raise ValueError("This adjective must be bound to a parent first")
        return self.parent_variable.label + "['" + self.label + "']"

    def __repr__(self):
        return self.full_label

    def view(self, *args, **kwargs):
        raise NotImplementedError()
        # TODO: Implement this aspect of the code that was in FuzzyVariable
        # Plot the active membership function (if any) heavier
        if key == self.active:
            lw = 2
        else:
            lw = 1


class FuzzyVariable(object):
    """
    Base class containing universe variable & associated membership functions.

    Parameters
    ----------
    universe : array-like
        Universe variable. Must be 1-dimensional and convertible to a NumPy
        array. Required.
    label : string
        Name of the universe variable. Optional.

    Methods
    -------

    Notes
    -----
    This class is designed as the base class underlying the Antecedent and
    Consequent classes, not for individual use.
    """
    def __init__(self, universe, label, defuzzy_method='centroid'):
        """
        Initialization of fuzzy variable

        Parameters
        ----------
        universe : array-like
            Universe variable. Must be 1-dimensional and convertible to a NumPy
            array.
        label : string
            Unique name of the universe variable, e.g., 'food' or 'velocity'.
        """
        self.universe = np.asarray(universe)
        self.label = label
        self.defuzzy_method = defuzzy_method
        self.adjectives = OrderedDict()
        self._id = id(self)
        self._crisp_value_accessed = False


    def __repr__(self):
        return "{0}: {1}".format(self.__name__, self.label)

    def __len__(self):
        return self.universe.size

    def __getitem__(self, key):
        """
        Calling variable['label'] will activate 'label' membership function.
        """
        if key in self.adjectives.keys():
            return self.adjectives[key]
        else:
            # Build a pretty list of available mf labels and raise an
            # informative error message
            options = ''
            i0 = len(self.adjectives) - 1
            i1 = len(self.adjectives) - 2
            for i, available_key in enumerate(self.adjectives.keys()):
                if i == i1:
                    options += "'" + str(available_key) + "', or "
                elif i == i0:
                    options += "'" + str(available_key) + "'."
                else:
                    options += "'" + str(available_key) + "'; "
            raise ValueError("Membership function '{0}' does not exist for "
                             "{1} {2}.\n"
                             "Available options: {3}".format(
                                 key, self.__name__, self.label, options))

    def __setitem__(self, key, item):
        """
        Enables new membership functions or adjectives to be added with the
        syntax::

          variable['new_label'] = new_mf
        """
        if isinstance(item, FuzzyVariableAdjective):
            if item.label != key:
                raise ValueError("Adjective's label must match new key")
            if item.parent_variable is not None:
                raise ValueError("Adjective must not already have a parent")
        else:
            # Try to create an adjective
            item = FuzzyVariableAdjective(key, np.asarray(item))

        if self._crisp_value_accessed:
            # TODO: Overcome this limitation
            raise ValueError("Cannot add adjectives after accessing the "
                             "crisp value of this variable.")

        mf = item.mf

        if mf.size != self.universe.size:
            raise ValueError("New membership function {0} must be equivalent "
                             "in length to the universe variable.\n"
                             "Expected {1}, got {2}.".format(
                                 key, self.universe.size, mf.size))

        if (mf.max() > 1. + 1e-6) or (mf.min() < 0 - 1e-6):
            raise ValueError("Membership function {0} contains values out of "
                             "range. Allowed range is [0, 1].".format(key))

        # If above pass, add the new membership function
        item.parent_variable = self
        self.adjectives[key] = item

    @property
    def crisp_value(self):
        """Derive crisp value based on membership of adjectives"""
        output_mf, cut_mfs = self._find_crisp_value()
        if len(cut_mfs) == 0:
            raise ValueError("No adjectives have memberships.  Make sure you "
                             "have at least one rule connected to this "
                             "variable and have run the rules calculation.")
        self._crisp_value_accessed = True
        return defuzz(self.universe, output_mf, self.defuzzy_method)

    @crisp_value.setter
    def crisp_value(self, value):
        """Propagate crisp value down to adjectives by calculating membership"""
        if len(self.adjectives) == 0:
            raise ValueError("Set Adjective membership function(s) first")

        for label, adj in self.adjectives.items():
            adj.membership_value = \
                                interp_membership(self.universe, adj.mf, value)
        self._crisp_value_accessed = True

    def _find_crisp_value(self):
        # Check we have some adjectives
        if len(self.adjectives.keys()) == 0:
            raise ValueError("Set Adjective membership function(s) first")

        # Initilize membership
        output_mf = np.zeros_like(self.universe, dtype=np.float64)

        # Build output membership function
        cut_mfs = {}
        for label, adj in self.adjectives.items():
            cut = adj.membership_value
            if cut is None:
                continue # No membership defined for this adjective
            cut_mfs[label] = np.minimum(cut, adj.mf)
            np.maximum(output_mf, cut_mfs[label], output_mf)

        return output_mf, cut_mfs

    def view(self, *args, **kwargs):
        """
        Visualize this variable and its membership functions with Matplotlib.
        Additionally, show the current output membership functions.
        """
        self._variable_figure_generator(self, *args, **kwargs)
        output_mf, cut_mfs = self._find_crisp_value()

        # Plot the output membership functions
        cut_plots = {}
        zeros = np.zeros_like(self.universe, dtype=np.float64)

        for label, mf_plot in self._plots.items():
            # Only attempt to plot those with cuts
            if label in cut_mfs:
                # Harmonize color between mf plots and filled overlays
                color = mf_plot[0].get_color()
                cut_plots[label] = self._ax.fill_between(
                    self.universe, zeros, cut_mfs[label],
                    facecolor=color, alpha=0.4)

        # Plot defuzzified output if available
        if len(cut_mfs) > 0:
            crip_value = defuzz(self.universe, output_mf, self.defuzzy_method)
            if crip_value is not None:
                y = interp_membership(self.universe, output_mf, crip_value)
                self._ax.plot([crip_value] * 2, [0, y],
                              color='k', lw=3, label='crisp value')

        self._fig.show()

    def _variable_figure_generator(self, *args, **kwargs):
        """
        Creates a base figure representation of this fuzzy variable.
        """
        # Assign plot to hidden attributes for bookkeeping in child classes
        self._fig, self._ax = plt.subplots()
        self._plots = {}

        # Formatting: limits
        self._ax.set_ylim([0, 1])
        self._ax.set_xlim([self.universe.min(), self.universe.max()])

        # Make the plots
        for key, adj in self.adjectives.items():
            self._plots[key] = self._ax.plot(self.universe,
                                             adj.mf,
                                             label=key,
                                             lw=1)

        # Place legend in upper left
        self._ax.legend(framealpha=0.5)

        # Ticks outside the axes
        self._ax.tick_params(direction='out')

        # Label the axes
        self._ax.set_ylabel('Membership')
        self._ax.set_xlabel(self.label)

        # Not returned - child classes use these attributes in .view() methods
        return None

    def automf(self, number=5, variable_type='quality', invert=False):
        """
        Automatically populates the universe with membership functions.

        Parameters
        ----------
        number : [3, 5, 7]
            Number of membership functions to create. Must be an odd integer.
            At present, only 3, 5, or 7 are supported.
        variable_type : string
            Type of variable this is. Accepted arguments are
            * 'quality' : Continuous variable, higher values are better.
            * 'quant' : Quantitative variable, no value judgements.
        invert : bool
            Reverses the naming order if True. Membership function peaks still
            march from lowest to highest.

        Notes
        -----
        This convenience function allows quick construction of fuzzy variables
        with overlapping, triangular membership functions.

        It uses a standard naming convention defined for ``'quality'`` as::

        * dismal
        * poor
        * mediocre
        * average (always middle)
        * decent
        * good
        * excellent

        and for ``'quant'`` as::

        * lowest
        * lower
        * low
        * average (always middle)
        * high
        * higher
        * highest

        where the names on either side of ``'average'`` are used as needed to
        create 3, 5, or 7 membership functions.
        """
        if variable_type.lower() == 'quality':
            names = ['dismal',
                     'poor',
                     'mediocre',
                     'average',
                     'decent',
                     'good',
                     'excellent']
        else:
            names = ['lowest',
                     'lower',
                     'low',
                     'average',
                     'high',
                     'higher',
                     'highest']

        if number == 3:
            if variable_type.lower() == 'quality':
                names = names[1:6:2]
            else:
                names = names[2:5]
        if number == 5:
            names = names[1:6]

        if invert is True:
            names = names[::-1]

        if number not in [3, 5, 7]:
            raise ValueError("Only number = 3, 5, or 7 supported.")

        limits = [self.universe.min(), self.universe.max()]
        universe_range = limits[1] - limits[0]
        widths = [universe_range / ((number - 1) / 2.)] * int(number)
        centers = np.linspace(limits[0], limits[1], number)

        abcs = [[c - w / 2, c, c + w / 2] for c, w in zip(centers, widths)]

        # Clear existing adjectives, if any
        self.adjectives = OrderedDict()
        if self.__name__ == 'Antecedent':
            self.output = OrderedDict()
        else:
            self.output = None

        # Repopulate
        for name, abc in zip(names, abcs):
            self[name] = trimf(self.universe, abc)
