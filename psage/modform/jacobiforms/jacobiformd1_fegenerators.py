r"""
Using restriction to scalar indices, we compute Jacobi forms of arbitrary index.  
"""

#===============================================================================
# 
# Copyright (C) 2012 Martin Raum
# 
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 3
# of the License, or (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful, 
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program; if not, see <http://www.gnu.org/licenses/>.
#
#===============================================================================

from psage.modform.fourier_expansion_framework.monoidpowerseries.monoidpowerseries_lazyelement import \
                                        EquivariantMonoidPowerSeries_lazy
from psage.modform.jacobiforms.jacobiformd1_dimensionformula import dimension__jacobi
from psage.modform.jacobiforms.jacobiformd1_fourierexpansion import JacobiFormD1FourierExpansionModule, \
                                                                    JacobiFormD1Filter
from psage.modform.jacobiforms.jacobiformd1nn_fourierexpansion import JacobiFormD1NNIndices, JacobiFormD1NNFilter, JacobiFormD1WeightCharacter
from psage.modform.jacobiforms.jacobiformd1nn_types import JacobiFormsD1NN, JacobiFormD1NN_Gamma
from sage.combinat.partition import number_of_partitions
from sage.libs.flint.fmpz_poly import Fmpz_poly  
from sage.matrix.constructor import matrix, zero_matrix
from sage.misc.cachefunc import cached_function
from sage.misc.functional import isqrt
from sage.misc.flatten import flatten
from sage.misc.misc import prod
from sage.modular.modform.constructor import ModularForms
from sage.modular.modform.element import ModularFormElement
from sage.modules.all import FreeModule, vector, span
from sage.rings.all import GF
from sage.rings.arith import binomial, factorial
from sage.rings.integer import Integer
from sage.rings.integer_ring import ZZ
from sage.rings.polynomial.polynomial_ring_constructor import PolynomialRing
from sage.rings.power_series_ring import PowerSeriesRing
from sage.rings.rational_field import QQ
from sage.quadratic_forms.all import QuadraticForm
from sage.sets.all import Set
from sage.structure.sage_object import SageObject
import operator
from copy import copy

#===============================================================================
# jacobi_form_d1_by_restriction
#===============================================================================

def jacobi_form_d1_by_restriction(precision, k, L, i) :
    r"""
    Lazy Fourier expansions of a basis of Jacobi forms (of arbitrary
    rank index).
    
    INPUT:
    
    - ``precision`` -- A filter for Fourier expansions of Jacobi forms. 
    
    - `k` -- An integer; The weight of the Jacobi forms.
    
    - `L` -- An even quadratic form; The index of the Jacobi forms.
    
    - `i` -- A nonnegative integer less the dimension of the considered
             space of Jacobi forms.
    
    OUTPUT:
    
    - A lazy element of the corresponding module of Fourier expansions (over `\QQ`).
    """
    expansion_ring = JacobiFormD1FourierExpansionModule(QQ, k, L)
    coefficients_factory = JacobiFormD1DelayedFactory__restriction( precision, k, L, i )
    
    return EquivariantMonoidPowerSeries_lazy(expansion_ring, precision, coefficients_factory.getcoeff)

#===============================================================================
# JacobiFormD1DelayedFactory__restriction
#===============================================================================

class JacobiFormD1DelayedFactory__restriction :
    def __init__(self, precision, k, L, i) :
        self.__precision = precision
        self.__weight = k
        self.__index = L
        self.__i = i
        
        self.__ch = JacobiFormD1WeightCharacter(k, L)
        
    def getcoeff(self, key, **kwds) :
        (ch, k) = key
        
        if ch != self.__ch :
            return 0
        else :
            return _coefficient_by_restriction( self.__precision, self.__weight, self.__index )[self.__i][k]                                    

#===============================================================================
# _find_complete_set_of_restriction_vectors
#===============================================================================

def _find_complete_set_of_restriction_vectors(L, R, additional_s = 0) :
    r"""
    Given a set R of elements in L^# (e.g. representatives for ( L^# / L ) / \pm 1)
    find a complete set of restriction vectors. (See [GKR])
    
    INPUT:
    
    - `L` -- A quadratic form.
    
    - `R` -- A list of tuples or vectors in L \otimes QQ (with
             given coordinates).
    
    OUTPUT:
    
    - A set S of pairs, the first of which is a vector corresponding to
      an element in L, and the second of which is an integer.
    
    TESTS::
    
        sage: from psage.modform.jacobiforms.jacobiformd1_fegenerators import _find_complete_set_of_restriction_vectors
        sage: from psage.modform.jacobiforms.jacobiformd1_fourierexpansion import *
        sage: indices = JacobiFormD1Indices(QuadraticForm(matrix(2, [2,1,1,2])))
        sage: _find_complete_set_of_restriction_vectors(indices.jacobi_index(), indices._r_representatives)        
        [((-1, 0), 0), ((-1, 0), -1), ((-1, 0), 1)]
    """
    R = [map(vector, rs) for rs in R]
    
    length_inc = 5
    max_length = 5
    cur_length = 1
    short_vectors = L.short_vector_list_up_to_length(max_length, True)
    
    S = list()
    restriction_space = FreeModule(ZZ, len(R)).span([])
    
    
    while (len(S) < len(R) + additional_s ) :
        while len(short_vectors[cur_length]) == 0 :
            cur_length += 1
            if max_length >= cur_length :
                max_length += length_inc
                short_vectors = L.short_vector_list_up_to_length(max_length, True)
                
        s = vector( short_vectors[cur_length].pop() )
        
        rcands = Set([ s.dot_product(r) for rs in R for r in rs ])
        
        for r in rcands :
            v = _eval_restriction_vector(R, s, r)
            if len(S) - restriction_space.rank() < additional_s or \
               v not in restriction_space :
                S.append((s, r))
                restriction_space = restriction_space + FreeModule(ZZ, len(R)).span([v])
                
                if len(S) == len(R) + additional_s :
                    break
    
    return S
    
#===============================================================================
# _eval_restriction_vector
#===============================================================================

def _eval_restriction_vector(R, s, r) :
    r"""
    For each list rs in R compute the multiplicity of s r' = r, r' in rs.
    
    INPUT:
    
    - `R` -- A list of list of vectors.
    
    - `s` -- A vector of the same length.
    
    - `r` -- An integer.
    
    OUTPUT:
    
    - A vector with integer entries that correspond to the elements
      of R in the given order.
    """
    return vector( len([ rp for rp in rs if s.dot_product(rp) == r ])
                   for rs in R )

#===============================================================================
# _local_restriction_matrix
#===============================================================================

def _local_restriction_matrix(R, S) :
    r"""
    Return a matrix whose rows correspond to the evaluations of the restriction
    vectors (s, r) in S.
    
    INPUT:
    
    - `R` -- A list of tuples or vectors in L \otimes QQ (with given coordinates).
    
    - `S` -- A list of pairs `(s, r)`, where `s` is a vector,
             and `r` is an integer.
             
    OUTPUT:
    
    - A matrix with integer entries.
    
    TESTS::

        sage: from psage.modform.jacobiforms.jacobiformd1_fourierexpansion import *
        sage: from psage.modform.jacobiforms.jacobiformd1_fegenerators import _find_complete_set_of_restriction_vectors
        sage: from psage.modform.jacobiforms.jacobiformd1_fegenerators import _local_restriction_matrix                
        sage: indices = JacobiFormD1Indices(QuadraticForm(matrix(2, [2,1,1,2])))
        sage: R = indices._r_representatives
        sage: S = _find_complete_set_of_restriction_vectors(indices.jacobi_index(), R, 4)        
        sage: _local_restriction_matrix(R, S)
        [1 1 1]
        [0 1 0]
        [0 0 1]
        [1 0 0]
        [0 1 1]
        [0 1 1]
        [1 1 1]
    """
    R = [map(vector, rs) for rs in R]
    
    return matrix([ _eval_restriction_vector(R, vector(s), r) for (s, r) in S ])

#===============================================================================
# _global_restriction_matrix
#===============================================================================

def _global_restriction_matrix(precision, S, weight_parity, find_relations = False) :
    r"""
    A matrix that maps the Fourier expansion of a Jacobi form of given precision
    to their restrictions with respect to the elements of S.
    
    INPUT:
    
    - ``precision`` -- An instance of JacobiFormD1Filter.
    
    - `S` -- A list of vectors.
    
    - ``weight_parity`` -- The parity of the weight of the considered Jacobi forms.
    
    - ``find_relation`` -- A boolean. If ``True``, then the restrictions to
                           nonreduced indices will also be computed.
                           
    TESTS::
    
        sage: from psage.modform.jacobiforms.jacobiformd1_fourierexpansion import *
        sage: from psage.modform.jacobiforms.jacobiformd1_fegenerators import _global_restriction_matrix
        sage: precision = JacobiFormD1Filter(5, QuadraticForm(matrix(2, [2,1,1,2]))
        sage: (global_restriction_matrix, row_groups, row_labels, column_labels) = _global_restriction_matrix(precision, [vector((1,0))], 12)
        sage: global_restriction_matrix
        [1 0 0 0 0 0 0 0 0]
        [0 1 4 0 0 0 0 0 0]
        [0 2 2 0 0 0 0 0 0]
        [0 2 0 1 4 0 0 0 0]
        [0 0 2 2 2 0 0 0 0]
        [0 0 2 2 0 1 4 0 0]
        [0 0 2 0 2 2 2 0 0]
        [0 0 0 0 2 2 0 1 4]
        [0 2 0 0 2 0 2 2 2]
        sage: (row_groups, row_labels, column_labels)
        ([((1, 0), 0, 9)], [{(0, 0): 0, (3, 0): 5, (3, 1): 6, (2, 1): 4, (2, 0): 3, (1, 0): 1, (4, 1): 8, (1, 1): 2, (4, 0): 7}], [(0, (0, 0)), (1, (0, 0)), (1, (0, 1)), (2, (0, 0)), (2, (0, 1)), (3, (0, 0)), (3, (0, 1)), (4, (0, 0)), (4, (0, 1))]
    """
    L = precision.jacobi_index()
    weight_parity = weight_parity % 2

    jacobi_indices = [ L(s) for s in S ]
    index_filters = dict( (m, list(JacobiFormD1NNFilter(precision.index(), m, reduced = not find_relations)))
                          for m in Set(jacobi_indices) )
    
    column_labels = list(precision)
    reductions = dict( (l, list()) for l in column_labels )
    for l in precision.monoid_filter() :
        (lred, sign) = precision.monoid().reduce(l)
        reductions[lred].append((l, sign)) 

    row_groups = [ len(index_filters[m]) for m in jacobi_indices ]
    row_groups = [ (s, sum(row_groups[:i]), row_groups[i]) for (i, s) in enumerate(S) ]
    row_labels = [ dict( (l, i) for (i, l) in enumerate(index_filters[m]) )
                   for m in jacobi_indices ]

    mat = zero_matrix(ZZ, sum(map(len, row_labels)), len(column_labels))
    
    for (cind, l) in enumerate(column_labels) :
        for ((n, r), sign) in reductions[l] :
            r = vector(r)
            for ((s, start, length), row_labels_dict) in zip(row_groups, row_labels) :
                try :
                    mat[start + row_labels_dict[(n, s.dot_product(r))], cind] += \
                        1 if weight_parity == 0 else sign
                except KeyError :
                    pass
    
    return (mat, row_groups, row_labels, column_labels)

#===============================================================================
# _global_relation_matrix
#===============================================================================

def _global_relation_matrix(precision, S, weight_parity) :
    r"""
    Deduce restrictions on the coefficients of a Jacobi form based on
    the specialization to Jacobi form of scalar index.
    
    INPUT:
    
    - ``precision`` -- An instance of JacobiFormD1Filter.
    
    - `S` -- A list of vectors.
    
    - ``weight_parity`` -- The parity of the weight of the considered Jacobi forms.
    """
    L = precision.jacobi_index()
    weight_parity = weight_parity % 2
    
    (mat, row_groups, row_labels, column_labels) = _global_restriction_matrix(precision, S, weight_parity, find_relations = True)
        
    reduced_index_indices = dict( (m, JacobiFormD1NNIndices(m)) for m in Set(L(s) for s in S) )
        
    relations = list()
    for ((s, start, length), row_labels_dict) in zip(row_groups, row_labels) :
        m = L(s)
        for (l, i) in row_labels_dict.iteritems() :
            (lred, sign) = reduced_index_indices[m].reduce(l)
            if lred == l :
                continue
            
            relations.append(mat.row(start + row_labels_dict[lred]) - (1 if weight_parity == 0 else sign) * mat.row(start + i))
    
    return (matrix(relations), column_labels)
    
#===============================================================================
# _coefficient_by_restriction
#===============================================================================

_coefficient_by_restriction__cache = dict()
def _coefficient_by_restriction( precision, k, L ) :
    r"""
    Compute the Fourier expansions of Jacobi forms of weight `k` and 
    index `L` (an even symmetric matrix) up to given precision.
    
    ALGORITHM:
    
    See [GKR12].
    
    INPUT:
    
    - ``precision`` -- A filter for Jacobi forms of arbitrary index.
    
    - `k` -- An integer.
    
    - `L` -- A quadratic form or an even symmetric matrix (over `\ZZ`).
    
    OUTPUT:
    
    - A list of elements of the corresponding Fourier expansion module.
    """
    try :
        Lmat = L.matrix()
    except AttributeError :
        Lmat = copy(L)
        L = QuadraticForm(Lmat)
    Lmat.set_immutable()
    
    global _coefficient_by_restriction__cache
    try :
        expansions = _coefficient_by_restriction__cache[(k, Lmat)]

        if expansions.precision() <= precision() :
            ## TODO: This should be checked in the framework
            return [ f.truncate(precision) for f in expansions ]
    except KeyError :
        pass
     
    
    dim = dimension__jacobi(k, Lmat)
    if dim == 0 :
        return []


    R = precision.monoid()._r_representatives
    print R
    S_extended = _find_complete_set_of_restriction_vectors(L, R)
    print S_extended
        
    S = list()
    for (s, _) in S_extended :
        if s not in S :
            S.append(s) 
    max_S_length = max([L(s) for s in S])

    (global_restriction_matrix, row_groups, row_labels, column_labels) = _global_restriction_matrix(precision, S, k)
    (global_relation_matrix, column_labels_restriction) = _global_relation_matrix(precision, flatten(L.short_vector_list_up_to_length(max_S_length + 1, True)[1:]), k)
    
    assert column_labels == column_labels_restriction
    
    jacobi_indices = Set( L(s) for (m, _, _) in row_groups )
    index_filters = dict( (m, JacobiFormD1NNFilter(precision.index(), m)) for m in jacobi_indices )
    jacobi_forms = dict( (m, JacobiFormsD1NN(QQ, JacobiFormD1NN_Gamma(k, m), prec) )
                         for (m, prec) in index_filters.iteritems() )

    forms = list()
    ch = JacobiFormD1WeightCharacter(k)
    for (m, (s, start, length), row_labels_dict) in zip(jacobi_indices, row_groups, row_labels) :
        for f in jacobi_forms[m].graded_submodule((k,m)).basis() :
            f = f.fourier_expansion()
            v = vector(ZZ, len(row_labels_dict))
            for (l, i) in row_labels_dict.iteritems() :
                v[i] = f[(ch, l)]
                
            forms.append(vector(   start*[0] + v.list()
                                 + (row_groups[-1][1] + row_groups[-1][2] - start - length)*[0] ))

    jacobi_expansions = global_restriction_matrix.row_module().intersection(span(forms)).intersection(global_relation_matrix.right_kernel())
    

    if jacobi_expansions.dimension() < dim :
        raise RuntimeError( "There is a bug in the implementation of the restriction method" )
    if jacobi_expansions.dimension() > dim :
        raise ValueError( "Could not construct enough restrictions to determine Fourier expansion uniquely" )
    
    
    fourier_expansion_module = JacobiFormD1FourierExpansionModule(QQ, k, L)
    characters = list(fourier_expansion_module.characters())
    ch = characters[0] if characters[0](-1) == (1 if k % 2 == 0 else -1) \
         else characters[1]
        
    expansions = list()
    for v in jacobi_expansions.basis() :
        expansions.append( fourier_expansion_module(dict( ((ch, l), c) for (l, c) in zip(column_labels, v) )) )
        
    return expansions
