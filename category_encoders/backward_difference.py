"""Backward difference contrast encoding"""

import copy
import pandas as pd
import numpy as np
from sklearn.base import BaseEstimator, TransformerMixin
from patsy.highlevel import dmatrix
from category_encoders.ordinal import OrdinalEncoder
from category_encoders.utils import get_obj_cols

__author__ = 'willmcginnis'


class BackwardDifferenceEncoder(BaseEstimator, TransformerMixin):
    """

    Parameters
    ----------

    verbose: int
        integer indicating verbosity of output. 0 for none.
    cols: list
        a list of columns to encode, if None, all string columns will be encoded
    drop_invariant: bool
        boolean for whether or not to drop columns with 0 variance
    return_df: bool
        boolean for whether to return a pandas DataFrame from transform (otherwise it will be a numpy array)

    Example
    -------
    >>> from category_encoders import BackwardDifferenceEncoder
    >>> from sklearn.datasets import fetch_20newsgroups_vectorized
    >>> bunch = fetch_20newsgroups_vectorized(subset="all")
    >>> X, y = bunch.data, bunch.target
    >>> enc = BackwardDifferenceEncoder(return_df=False).fit(X, y)
    >>> numeric_dataset = enc.transform(X)

    References
    ----------

    .. [1] Contrast Coding Systems for categorical variables.  UCLA: Statistical Consulting Group. from
    http://www.ats.ucla.edu/stat/r/library/contrast_coding.

    .. [2] Gregory Carey (2003). Coding Categorical Variables, from
    http://psych.colorado.edu/~carey/Courses/PSYC5741/handouts/Coding%20Categorical%20Variables%202006-03-03.pdf


    """

    def __init__(self, verbose=0, cols=None, drop_invariant=False, return_df=True):
        self.return_df = return_df
        self.drop_invariant = drop_invariant
        self.drop_cols = []
        self.verbose = verbose
        self.cols = cols
        self.ordinal_encoder = None
        self._dim = None

    def fit(self, X, y=None, **kwargs):
        """Fits an ordinal encoder to produce a consistent mapping across applications and optionally finds
        generally invariant columns to drop consistently.

        Parameters
        ----------

        X : array-like, shape = [n_samples, n_features]
            Training vectors, where n_samples is the number of samples
            and n_features is the number of features.
        y : array-like, shape = [n_samples]
            Target values.

        Returns
        -------

        self : encoder
            Returns self.

        """

        # if the input dataset isn't already a dataframe, convert it to one (using default column names)
        # first check the type
        if not isinstance(X, pd.DataFrame):
            if isinstance(X, list):
                X = pd.DataFrame(np.array(X))
            elif isinstance(X, (np.generic, np.ndarray)):
                X = pd.DataFrame(X)
            else:
                raise ValueError('Unexpected input type: %s' % (str(type(X))))

        self._dim = X.shape[1]

        # if columns aren't passed, just use every string column
        if self.cols is None:
            self.cols = get_obj_cols(X)

        # train an ordinal pre-encoder
        self.ordinal_encoder = OrdinalEncoder(verbose=self.verbose, cols=self.cols)
        self.ordinal_encoder = self.ordinal_encoder.fit(X)

        # drop all output columns with 0 variance.
        if self.drop_invariant:
            self.drop_cols = []
            X_temp = self.transform(X)
            self.drop_cols = [x for x in X_temp.columns.values if X_temp[x].var() <= 10e-5]

        return self

    def transform(self, X):
        """Perform the transformation to new categorical data.

        Parameters
        ----------

        X : array-like, shape = [n_samples, n_features]

        Returns
        -------

        p : array, shape = [n_samples, n_numeric + N]
            Transformed values with encoding applied.

        """

        if self._dim is None:
            raise ValueError('Must train encoder before it can be used to transform data.')

        # first check the type
        if not isinstance(X, pd.DataFrame):
            if isinstance(X, list):
                X = pd.DataFrame(np.array(X))
            elif isinstance(X, (np.generic, np.ndarray)):
                X = pd.DataFrame(X)
            else:
                raise ValueError('Unexpected input type: %s' % (str(type(X))))

        # then make sure that it is the right size
        if X.shape[1] != self._dim:
            raise ValueError('Unexpected input dimension %d, expected %d' % (X.shape[1], self._dim, ))

        if not self.cols:
            return X

        X = self.ordinal_encoder.transform(X)
        X = self.backward_difference_coding(X, cols=self.cols)

        if self.drop_invariant:
            for col in self.drop_cols:
                X.drop(col, 1, inplace=True)

        if self.return_df:
            return X
        else:
            return X.values

    @staticmethod
    def backward_difference_coding(X_in, cols=None):
        """

        :param X:
        :return:
        """

        X = X_in.copy(deep=True)

        if cols is None:
            cols = X.columns.values
            pass_thru = []
        else:
            pass_thru = [col for col in X.columns.values if col not in cols]

        bin_cols = []
        for col in cols:
            mod = dmatrix("C(%s, Diff)" % (col, ), X)
            for dig in range(len(mod[0])):
                X[col + '_%d' % (dig, )] = mod[:, dig]
                bin_cols.append(col + '_%d' % (dig, ))

        X = X.reindex(columns=bin_cols + pass_thru)
        X.fillna(0.0)

        return X