"""
Script to run the SP aircraft model
"""

# GPkit tools
from gpkit import units, Model
from gpkit import Variable, Model, units, SignomialsEnabled, SignomialEquality, Vectorize
from gpkit.constraints.bounded import Bounded as BCS

# Constant relaxation heuristic for SP solve
from relaxed_constants import relaxed_constants, post_process

# Mission model
from aircraft import Mission

# Substitution dictionaries for different aircraft
from subs.optimal_D8 import get_optimal_D8_subs
from subs.optimal_777300ER import get_optimal_777300ER_subs
from subs.optimal_737 import get737_optimal_subs
from subs.b737_M072 import get_M072_737_subs
from subs.D8_no_BLI import get_D8_no_BLI_subs
from subs.D8_eng_wing import get_D8_eng_wing_subs

# Plotting tools
from gen_plots import *

# File for calculating values after solution
from post_compute import post_compute

# Solution check tool relative to TASOPT
from percent_diff import percent_diff

# VSP visualization tools
from saveSol import updateOpenVSP, genDesFile, genDesFileSweep

def run_optimal_777(objective, fixedBPR, pRatOpt, mutategparg):
    # User definitions
    Nclimb = 3
    Ncruise = 2
    Nmission = 1
    aircraft = 'optimal777'

    m = Mission(Nclimb, Ncruise, objective, aircraft, Nmission)
    
    substitutions = get_optimal_777300ER_subs()

    substitutions.update({
        'R_{req}': 6000.,
        'n_{pass}': 450.,
    })

    if fixedBPR:
        substitutions.update({
            '\\alpha_{max}': 8.62, 
        })

    if pRatOpt:
        del substitutions['\pi_{f_D}']
##        del substitutions['\pi_{lc_D}']
##        del substitutions['\pi_{hc_D}']

    m.substitutions.update(substitutions)
    m = Model(m.cost, BCS(m))
    m_relax = relaxed_constants(m, None, ['M_{takeoff}', '\\theta_{db}'])

    sol = m_relax.localsolve(verbosity=4, iteration_limit=200, reltol=0.01, mutategp=mutategparg)
    post_process(sol)

    percent_diff(sol, 'b777300ER', Nclimb)

    post_compute(sol, Nclimb)

    return sol

def run_optimal_D8(objective, fixedBPR, pRatOpt, mutategparg):
    # User definitions
    Nclimb = 3
    Ncruise = 2
    Nmission = 1
    aircraft = 'optimalD8'

    m = Mission(Nclimb, Ncruise, objective, aircraft, Nmission)
    
    substitutions = get_optimal_D8_subs()

    if Nmission == 2:
        substitutions.update({
            'R_{req}': [3000.*units('nmi'), 2000.*units('nmi')], #,2500.*units('nmi')
            'n_{pass}': [180., 180.], #,140.
        })
    else:
        substitutions.update({
            'R_{req}': 3000.*units('nmi'),
            'n_{pass}': 180.,
        })

    if fixedBPR:
        substitutions.update({
            '\\alpha_{max}': 6.97,
        })

    if pRatOpt:
        #del substitutions['\pi_{f_D}']
        del substitutions['\pi_{lc_D}']
        del substitutions['\pi_{hc_D}']

    m = Model(m.cost, BCS(m))
    m.substitutions.update(substitutions)

    m_relax = relaxed_constants(m, None, ['M_{takeoff}', '\\theta_{db}'])

    sol = m_relax.localsolve(verbosity=4, iteration_limit=200, reltol=0.01, mutategp=mutategparg, skipsweepfailures=True)
    post_process(sol)

    percent_diff(sol, 'D82', Nclimb)

    post_compute(sol, Nclimb)

    return sol

def run_optimal_737(objective, fixedBPR, pRatOpt, mutategparg):
    # User definitions
    Nclimb = 3
    Ncruise = 2
    Nmission = 1
    aircraft = 'optimal737'

    m = Mission(Nclimb, Ncruise, objective, aircraft, Nmission)
    
    substitutions = get737_optimal_subs()

    if Nmission == 4:
        substitutions.update({
            'R_{req}': [3000.*units('nmi'),2500.*units('nmi'),2000.*units('nmi'),1000.*units('nmi')], #,2500.*units('nmi')
            'n_{pass}': [180., 180., 180., 180.], #, 140.
        })
    elif Nmission == 2:
        substitutions.update({
            'R_{req}': [3000.*units('nmi'),2000.*units('nmi'),], #,2500.*units('nmi')
            'n_{pass}': [180., 180.], #, 140.
        })
    else:
        substitutions.update({
           'R_{req}': 3000.*units('nmi'),
           'n_{pass}': 180.,
        })

    if fixedBPR:
        substitutions.update({
            '\\alpha_{max}': 6.97,
        })
        
    if pRatOpt:
        #del substitutions['\pi_{f_D}']
        del substitutions['\pi_{lc_D}']
        del substitutions['\pi_{hc_D}']

    m.substitutions.update(substitutions)

    m = Model(m.cost, BCS(m))
    m_relax = relaxed_constants(m, None, ['M_{takeoff}', '\\theta_{db}'])

    sol = m_relax.localsolve(verbosity=4, iteration_limit=200, reltol=0.01, mutategp=mutategparg)
    #post_process(sol)

    #percent_diff(sol, 'b737800', Nclimb)

    #post_compute(sol, Nclimb)

    return sol

def run_M072_737(objective, fixedBPR, pRatOpt, mutategparg):
    # User definitions
    Nclimb = 3
    Ncruise = 2
    Nmission = 1
    aircraft = 'M072_737'

    m = Mission(Nclimb, Ncruise, objective, aircraft, Nmission)
    
    substitutions = get_M072_737_subs()

    if Nmission > 1:
        substitutions.update({
            'R_{req}': [3000.*units('nmi'),2500.*units('nmi')],
            'n_{pass}': [180., 180.],
        })
    else:
        substitutions.update({
            'R_{req}': 3000.*units('nmi'),
            'n_{pass}': 180.,
        })        

    if fixedBPR:
        substitutions.update({
            '\\alpha_{max}': 6.97,
        })
        
    if pRatOpt:
        del substitutions['\pi_{f_D}']
##        del substitutions['\pi_{lc_D}']
##        del substitutions['\pi_{hc_D}']

    m.substitutions.update(substitutions)

    m = Model(m.cost, BCS(m))
    m_relax = relaxed_constants(m, None, ['M_{takeoff}', '\\theta_{db}'])

    sol = m_relax.localsolve(verbosity=4, iteration_limit=200, reltol=0.01, mutategp=mutategparg)
    post_process(sol)

    percent_diff(sol, aircraft, Nclimb)

    post_compute(sol, Nclimb)

    return sol

def run_D8_eng_wing(objective, fixedBPR, pRatOpt, mutategparg):
    # User definitions
    Nclimb = 3
    Ncruise = 2
    Nmission = 1
    aircraft = 'D8_eng_wing'

    m = Mission(Nclimb, Ncruise, objective, aircraft, Nmission)
    
    substitutions = get_D8_eng_wing_subs()

    if Nmission > 1:
        substitutions.update({
            'R_{req}': [3000.*units('nmi'),2500.*units('nmi')],
            'n_{pass}': [180., 180.],
        })
    else:
        substitutions.update({
            'n_{pass}': 180.,
            'R_{req}': 3000.*units('nmi'),
        })        

    if fixedBPR:
        substitutions.update({
            '\\alpha_{max}': 6.97,
        })
        
    if pRatOpt:
        del substitutions['\pi_{f_D}']
##        del substitutions['\pi_{lc_D}']
##        del substitutions['\pi_{hc_D}']

    m.substitutions.update(substitutions)
    m = Model(m.cost, BCS(m))
    m_relax = relaxed_constants(m, None, ['M_{takeoff}', '\\theta_{db}'])

    sol = m_relax.localsolve(verbosity=4, iteration_limit=200, reltol=0.01, mutategp=mutategparg)
    post_process(sol)

    percent_diff(sol, 'b737800', Nclimb)

    post_compute(sol, Nclimb)

    return sol

def run_D8_no_BLI(objective, fixedBPR, pRatOpt, mutategparg):
    # User definitions
    Nclimb = 3
    Ncruise = 2
    Nmission = 1
    aircraft = 'D8_no_BLI'

    m = Mission(Nclimb, Ncruise, objective, aircraft, Nmission)
    
    substitutions = get_D8_no_BLI_subs()

    if Nmission > 1:
        substitutions.update({
            'R_{req}': [3000.*units('nmi'),2500.*units('nmi')],
            'n_{pass}': [180., 180.],
        })
    else:
        substitutions.update({
            'R_{req}': 3000.*units('nmi'),
            'n_{pass}': 180.,
        })        

    if fixedBPR:
        substitutions.update({
            '\\alpha_{max}': 6.97,
        })
        
    if pRatOpt:
        del substitutions['\pi_{f_D}']
##        del substitutions['\pi_{lc_D}']
##        del substitutions['\pi_{hc_D}']

    m.substitutions.update(substitutions)
    m = Model(m.cost, BCS(m))
    m_relax = relaxed_constants(m, None, ['M_{takeoff}', '\\theta_{db}'])

    sol = m_relax.localsolve(verbosity=4, iteration_limit=200, reltol=0.01, mutategp=mutategparg)
    post_process(sol)

    percent_diff(sol, 'D82', Nclimb)

    post_compute(sol, Nclimb)

    return sol

def test():
    run_optimal_737('W_{f_{total}}', True, False, True)

##    OLD CODE DOESN'T CURRENTLY WORK
    
##def run_737800(objective = 'W_{f_{total}}'):
##    # User definitions
##    Nclimb = 3
##    Ncruise = 2
##    Nmission = 1
##    aircraft = 'b737800'
##
##    m = Mission(Nclimb, Ncruise, objective, aircraft, Nmission)
##    
##    substitutions = getb737800subs()
##
##    substitutions.update({
###                'n_{pass}': 180.,
##        'R_{req}': 3000.*units('nmi'),
##    })
##
##    m.substitutions.update(substitutions)
##
##    m = Model(m.cost, BCS(m))
##    m_relax = relaxed_constants(m, None, ['M_{takeoff}', '\\theta_{db}'])
##
##    sol = m_relax.localsolve(verbosity=4, iteration_limit=200, reltol=0.01)
##
##    percent_diff(sol, aircraft, Nclimb)
##
##    post_compute(sol, Nclimb)
##
##    return sol
##
##def run_D82(objective = 'W_{f_{total}}'):
##    # User definitions
##    Nclimb = 3
##    Ncruise = 2
##    Nmission = 1
##    aircraft = 'D82'
##
##    m = Mission(Nclimb, Ncruise, objective, aircraft, Nmission)
##    
##    substitutions = getD82subs()
##
##    substitutions.update({
###                'n_{pass}': 180.,
##        'R_{req}': 3000.*units('nmi'),
##    })
##
##    m.substitutions.update(substitutions)
##    m = Model(m.cost, BCS(m))
##    m_relax = relaxed_constants(m, None, ['M_{takeoff}', '\\theta_{db}'])
##
##    sol = m_relax.localsolve(verbosity=4, iteration_limit=200, reltol=0.01)
##    post_process(sol)
##
##    percent_diff(sol, aircraft, Nclimb)
##
##    post_compute(sol, Nclimb)
##
##    return sol
##
##def run_D12(objective, fixedBPR, pRatOpt, mutategparg):
##    # User definitions
##    Nclimb = 3
##    Ncruise = 2
##    Nmission = 1
##    aircraft = 'D12'
##
##    m = Mission(Nclimb, Ncruise, objective, aircraft, Nmission)
##    
##    substitutions = get_D12_subs()
##
##    substitutions.update({
###                'n_{pass}': 500.,
##        'R_{req}': 5600.*units('nmi'),
##    })
##
##    if fixedBPR:
##        substitutions.update({
##            '\\alpha_{max}': 8.009,
##        })
##
##    if pRatOpt:
##        del substitutions['\pi_{f_D}']
####        del substitutions['\pi_{lc_D}']
####        del substitutions['\pi_{hc_D}']
##
##    m.substitutions.update(substitutions)
##    m = Model(m.cost, BCS(m))
##    m_relax = relaxed_constants(m, None, ['M_{takeoff}', '\\theta_{db}'])
##
##    sol = m_relax.localsolve(verbosity=4, iteration_limit=200, reltol=0.01)
##    post_process(sol)
##
##    percent_diff(sol, aircraft, Nclimb)
##
##    post_compute(sol, Nclimb)
##
##    return sol
##

##
    

##
##def run_M08_D8_eng_wing(objective, fixedBPR, pRatOpt, mutategparg):
##    # User definitions
##    Nclimb = 3
##    Ncruise = 2
##    Nmission = 1
##    aircraft = 'M08_D8_eng_wing'
##
##    m = Mission(Nclimb, Ncruise, objective, aircraft, Nmission)
##    
##    substitutions = getM08_D8_eng_wing_subs()
##
##    substitutions.update({
###                'n_{pass}': 180.,
##        'R_{req}': 3000.*units('nmi'),
##    })
##
##    if fixedBPR:
##        substitutions.update({
##            '\\alpha_{max}': 6.97,
##        })
##
##    if pRatOpt:
##        del substitutions['\pi_{f_D}']
####        del substitutions['\pi_{lc_D}']
####        del substitutions['\pi_{hc_D}']
##
##    m.substitutions.update(substitutions)
##
##    m_relax = relaxed_constants(m, None, ['M_{takeoff}', '\\theta_{db}'])
##
##    sol = m_relax.localsolve(verbosity=4, iteration_limit=200, reltol=0.01)
##    post_process(sol)
##
##    percent_diff(sol, 'D82', Nclimb)
##
##    post_compute(sol, Nclimb)
##
##    return sol
##
##def run_M08_D8(objective, fixedBPR, pRatOpt, mutategparg):
##    # User definitions
##    Nclimb = 3
##    Ncruise = 2
##    Nmission = 1
##    aircraft = 'M08D8'
##
##    m = Mission(Nclimb, Ncruise, objective, aircraft, Nmission)
##    
##    substitutions = subs_M08_D8()
##
##    substitutions.update({
###                'n_{pass}': 180.,
##        'R_{req}': 3000.*units('nmi'),
##    })
##
##    if fixedBPR:
##        substitutions.update({
##            '\\alpha_{max}': 6.97,
##        })
##
##    if pRatOpt:
##        del substitutions['\pi_{f_D}']
####        del substitutions['\pi_{lc_D}']
####        del substitutions['\pi_{hc_D}']
##        
##    m.substitutions.update(substitutions)
##    m = Model(m.cost, BCS(m))
##    m_relax = relaxed_constants(m, None, ['M_{takeoff}', '\\theta_{db}'])
##
##    sol = m_relax.localsolve(verbosity=4, iteration_limit=200, reltol=0.01)
##    post_process(sol)
##
##    percent_diff(sol, 'D82', Nclimb)
##
##    post_compute(sol, Nclimb)
##
##    return sol
##
##def run_M08_D8_no_BLI(objective, fixedBPR, pRatOpt, mutategparg):
##    # User definitions
##    Nclimb = 3
##    Ncruise = 2
##    Nmission = 1
##    aircraft = 'M08D8_noBLI'
##
##    m = Mission(Nclimb, Ncruise, objective, aircraft, Nmission)
##    
##    substitutions = get_subs_M08_D8_noBLI()
##
##    substitutions.update({
###                'n_{pass}': 180.,
##        'R_{req}': 3000.*units('nmi'),
##    })
##
##    if fixedBPR:
##        substitutions.update({
##            '\\alpha_{max}': 6.97,
##        })
##
##    if pRatOpt:
##        del substitutions['\pi_{f_D}']
####        del substitutions['\pi_{lc_D}']
####        del substitutions['\pi_{hc_D}']
##        
##    m.substitutions.update(substitutions)
##    m = Model(m.cost, BCS(m))
##    m_relax = relaxed_constants(m, None, ['M_{takeoff}', '\\theta_{db}'])
##
##    sol = m_relax.localsolve(verbosity=4, iteration_limit=200, reltol=0.01)
##    post_process(sol)
##
##    percent_diff(sol, 'D82', Nclimb)
##
##    post_compute(sol, Nclimb)
##
##    return sol
##
##def run_777300ER(objective = 'W_{f_{total}}'):
##    # User definitions
##    Nclimb = 3
##    Ncruise = 2
##    Nmission = 1
##    aircraft = 'b777300ER'
##
##    m = Mission(Nclimb, Ncruise, objective, aircraft, Nmission)
##    
##    substitutions = getb777300ERsubs()
##
##    substitutions.update({
####        'n_{pass}': [450.],
##        'R_{req}': 6000.*units('nmi'),
##    })
##
##    m.substitutions.update(substitutions)
##    m = Model(m.cost, BCS(m))
##    m_relax = relaxed_constants(m, None, ['M_{takeoff}', '\\theta_{db}'])
##
##    sol = m_relax.localsolve(verbosity=4, iteration_limit=200, reltol=0.01)
##    post_process(sol)
##
##    percent_diff(sol, aircraft, Nclimb)
##
##    post_compute(sol, Nclimb)
##
##    return sol
##
##
##
##def run_M08_optimal_777(objective, fixedBPR, pRatOpt, mutategparg):
##    # User definitions
##    Nclimb = 3
##    Ncruise = 2
##    Nmission = 1
##    aircraft = 'optimal777_M08'
##
##    m = Mission(Nclimb, Ncruise, objective, aircraft, Nmission)
##    
##    substitutions = get_optimal_777300ER_M08_subs()
##
##    substitutions.update({
####        'n_{pass}': [450.],
##        'R_{req}': [6000.],
##    })
##
##    if fixedBPR:
##        substitutions.update({
##            '\\alpha_{max}': 8.62, 
##        })
##
##    if pRatOpt:
##        del substitutions['\pi_{f_D}']
####        del substitutions['\pi_{lc_D}']
####        del substitutions['\pi_{hc_D}']
##
##    m.substitutions.update(substitutions)
##    m = Model(m.cost, BCS(m))
##    m_relax = relaxed_constants(m, None, ['M_{takeoff}', '\\theta_{db}'])
##
##    sol = m_relax.localsolve(verbosity=4, iteration_limit=200, reltol=0.01)
##    post_process(sol)
##
##    percent_diff(sol, 'b777300ER', Nclimb)
##
##    post_compute(sol, Nclimb)
##
##    return sol
##
##def run_M072_optimal_777(objective, fixedBPR, pRatOpt, mutategparg):
##    # User definitions
##    Nclimb = 3
##    Ncruise = 2
##    Nmission = 1
##    aircraft = 'optimal777_M072'
##
##    m = Mission(Nclimb, Ncruise, objective, aircraft, Nmission)
##    
##    substitutions = get_optimal_777300ER_M072_subs()
##
##    substitutions.update({
####        'n_{pass}': [450.],
##        'R_{req}': [6000.],
##    })
##
##    if fixedBPR:
##        substitutions.update({
##            '\\alpha_{max}': 8.62, 
##        })
##
##    if pRatOpt:
##        del substitutions['\pi_{f_D}']
####        del substitutions['\pi_{lc_D}']
####        del substitutions['\pi_{hc_D}']
##
##    m.substitutions.update(substitutions)
##    m = Model(m.cost, BCS(m))
##    m_relax = relaxed_constants(m, None, ['M_{takeoff}', '\\theta_{db}'])
##
##    sol = m_relax.localsolve(verbosity=4, iteration_limit=200, reltol=0.01)
##    post_process(sol)
##
##    percent_diff(sol, 'b777300ER', Nclimb)
##
##    post_compute(sol, Nclimb)
##
##    return sol
##
##def run_D8_big(objective, fixedBPR, pRatOpt, mutategparg):
##    # User definitions
##    Nclimb = 3
##    Ncruise = 2
##    Nmission = 1
##    aircraft = 'D8big'
##
##    m = Mission(Nclimb, Ncruise, objective, aircraft, Nmission)
##    
##    substitutions = getD8bigsubs()
##
##    substitutions.update({
###                'n_{pass}': 180.,
##        'R_{req}': 6000.*units('nmi'),
##    })
##
##    if fixedBPR:
##        substitutions.update({
##            '\\alpha_{max}': 8.62, 
##        })
##
##    if pRatOpt:
##        del substitutions['\pi_{f_D}']
####        del substitutions['\pi_{lc_D}']
####        del substitutions['\pi_{hc_D}']
##        
##    m.substitutions.update(substitutions)
##    m = Model(m.cost, BCS(m))
##    m_relax = relaxed_constants(m, None, ['M_{takeoff}', '\\theta_{db}'])
##
##    sol = m_relax.localsolve(verbosity=4, iteration_limit=200, reltol=0.01)
##    post_process(sol)
##
##    percent_diff(sol, 'b777300ER', Nclimb)
##
##    post_compute(sol, Nclimb)
##
##    return sol
##
##def run_D8_big_no_BLI(objective, fixedBPR, pRatOpt, mutategparg):
##    # User definitions
##    Nclimb = 3
##    Ncruise = 2
##    Nmission = 1
##    aircraft = 'D8big_no_BLI'
##
##    m = Mission(Nclimb, Ncruise, objective, aircraft, Nmission)
##    
##    substitutions = getD8big_noBLI_subs()
##
##    substitutions.update({
###                'n_{pass}': 180.,
##        'R_{req}': 6000.*units('nmi'),
##    })
##
##    if fixedBPR:
##        substitutions.update({
##            '\\alpha_{max}': 8.62, 
##        })
##
##    if pRatOpt:
##        del substitutions['\pi_{f_D}']
####        del substitutions['\pi_{lc_D}']
####        del substitutions['\pi_{hc_D}']
##        
##    m.substitutions.update(substitutions)
##    m = Model(m.cost, BCS(m))
##    m_relax = relaxed_constants(m, None, ['M_{takeoff}', '\\theta_{db}'])
##
##    sol = m_relax.localsolve(verbosity=4, iteration_limit=200, reltol=0.01)
##    post_process(sol)
##
##    percent_diff(sol, 'b777300ER', Nclimb)
##
##    post_compute(sol, Nclimb)
##
##    return sol
##
##def run_M072_D8_big_no_BLI(objective, fixedBPR, pRatOpt, mutategparg):
##    # User definitions
##    Nclimb = 3
##    Ncruise = 2
##    Nmission = 1
##    aircraft = 'D8big_no_BLI'
##
##    m = Mission(Nclimb, Ncruise, objective, aircraft, Nmission)
##    
##    substitutions = getD8big_M072_noBLI_subs()
##
##    substitutions.update({
###                'n_{pass}': 180.,
##        'R_{req}': 6000.*units('nmi'),
##    })
##
##    if fixedBPR:
##        substitutions.update({
##            '\\alpha_{max}': 8.62, 
##        })
##
##    if pRatOpt:
##        del substitutions['\pi_{f_D}']
####        del substitutions['\pi_{lc_D}']
####        del substitutions['\pi_{hc_D}']
##        
##    m.substitutions.update(substitutions)
##    m = Model(m.cost, BCS(m))
##    m_relax = relaxed_constants(m, None, ['M_{takeoff}', '\\theta_{db}'])
##
##    sol = m_relax.localsolve(verbosity=4, iteration_limit=200, reltol=0.01)
##    post_process(sol)
##
##    percent_diff(sol, 'b777300ER', Nclimb)
##
##    post_compute(sol, Nclimb)
##
##    return sol
##
##def run_D8_big_eng_wing(objective, fixedBPR, pRatOpt, mutategparg):
##    # User definitions
##    Nclimb = 3
##    Ncruise = 2
##    Nmission = 1
##    aircraft = 'D8big_eng_wing'
##
##    m = Mission(Nclimb, Ncruise, objective, aircraft, Nmission)
##    
##    substitutions = getD8big_eng_wing_subs()
##
##    substitutions.update({
###                'n_{pass}': 180.,
##        'R_{req}': 6000.*units('nmi'),
##    })
##
##    if fixedBPR:
##        substitutions.update({
##            '\\alpha_{max}': 8.62, 
##        })
##
##    if pRatOpt:
##        del substitutions['\pi_{f_D}']
####        del substitutions['\pi_{lc_D}']
####        del substitutions['\pi_{hc_D}']
##        
##    m.substitutions.update(substitutions)
##    m = Model(m.cost, BCS(m))
##    m_relax = relaxed_constants(m, None, ['M_{takeoff}', '\\theta_{db}'])
##
##    sol = m_relax.localsolve(verbosity=4, iteration_limit=200, reltol=0.01)
##    post_process(sol)
##
##    percent_diff(sol, 'b777300ER', Nclimb)
##
##    post_compute(sol, Nclimb)
##
##    return sol
##
##def run_M072_D8_big_eng_wing(objective, fixedBPR, pRatOpt, mutategparg):
##    # User definitions
##    Nclimb = 3
##    Ncruise = 2
##    Nmission = 1
##    aircraft = 'D8big_eng_wing_M072'
##
##    m = Mission(Nclimb, Ncruise, objective, aircraft, Nmission)
##    
##    substitutions = getD8big_M072_eng_wing_subs()
##
##    substitutions.update({
###                'n_{pass}': 180.,
##        'R_{req}': 6000.*units('nmi'),
##    })
##
##    if fixedBPR:
##        substitutions.update({
##            '\\alpha_{max}': 8.62, 
##        })
##
##    if pRatOpt:
##        del substitutions['\pi_{f_D}']
####        del substitutions['\pi_{lc_D}']
####        del substitutions['\pi_{hc_D}']
##        
##    m.substitutions.update(substitutions)
##    m = Model(m.cost, BCS(m))
##    m_relax = relaxed_constants(m, None, ['M_{takeoff}', '\\theta_{db}'])
##
##    sol = m_relax.localsolve(verbosity=4, iteration_limit=200, reltol=0.01)
##    post_process(sol)
##
##    percent_diff(sol, 'b777300ER', Nclimb)
##
##    post_compute(sol, Nclimb)
##
##    return sol
##
##
##def run_D8_big_M072(objective, fixedBPR, pRatOpt, mutategparg):
##    # User definitions
##    Nclimb = 3
##    Ncruise = 2
##    Nmission = 1
##    aircraft = 'D8big'
##
##    m = Mission(Nclimb, Ncruise, objective, aircraft, Nmission)
##    
##    substitutions = getD8big_M072_subs()
##
##    substitutions.update({
###                'n_{pass}': 180.,
##        'R_{req}': 6000.*units('nmi'),
##    })
##
##    if fixedBPR:
##        substitutions.update({
##            '\\alpha_{max}': 8.62, 
##        })
##
##    if pRatOpt:
##        del substitutions['\pi_{f_D}']
####        del substitutions['\pi_{lc_D}']
####        del substitutions['\pi_{hc_D}']
##        
##    m.substitutions.update(substitutions)
##    m = Model(m.cost, BCS(m))
##    m_relax = relaxed_constants(m, None, ['M_{takeoff}', '\\theta_{db}'])
##
##    sol = m_relax.localsolve(verbosity=4, iteration_limit=200, reltol=0.01)
##    post_process(sol)
##
##    percent_diff(sol, 'b777300ER', Nclimb)
##
##    post_compute(sol, Nclimb)
##
##    return sol
##
##def run_D8_big_M08(objective, fixedBPR, pRatOpt, mutategparg):
##    # User definitions
##    Nclimb = 3
##    Ncruise = 2
##    Nmission = 1
##    aircraft = 'D8big'
##
##    m = Mission(Nclimb, Ncruise, objective, aircraft, Nmission)
##    
##    substitutions = getD8big_M08_subs()
##
##    substitutions.update({
###                'n_{pass}': 180.,
##        'R_{req}': 6000.*units('nmi'),
##    })
##
##    if fixedBPR:
##        substitutions.update({
##            '\\alpha_{max}': 8.62, 
##        })
##
##    if pRatOpt:
##        del substitutions['\pi_{f_D}']
####        del substitutions['\pi_{lc_D}']
####        del substitutions['\pi_{hc_D}']
##        
##    m.substitutions.update(substitutions)
##    m = Model(m.cost, BCS(m))
##    m_relax = relaxed_constants(m, None, ['M_{takeoff}', '\\theta_{db}'])
##
##    sol = m_relax.localsolve(verbosity=4, iteration_limit=200, reltol=0.01)
##    post_process(sol)
##
##    percent_diff(sol, 'b777300ER', Nclimb)
##
##    post_compute(sol, Nclimb)
##
##    return sol
##
##def run_optimal_RJ(objective, fixedBPR, pRatOpt, mutategparg):
##    # User definitions
##    Nclimb = 3
##    Ncruise = 2
##    Nmission = 1
##    aircraft = 'optimalRJ'
##
##    m = Mission(Nclimb, Ncruise, objective, aircraft, Nmission)
##    
##    substitutions = get_optimal_RJ_subs()
##
##    substitutions.update({
####        'n_{pass}': [90.],
##        'R_{req}': [1500.],
##    })
##
##    if fixedBPR:
##        substitutions.update({
##            '\\alpha_{max}': 5.6958, 
##        })
##
##    if pRatOpt:
##        del substitutions['\pi_{f_D}']
####        del substitutions['\pi_{lc_D}']
####        del substitutions['\pi_{hc_D}']
##
##    m.substitutions.update(substitutions)
##    m = Model(m.cost, BCS(m))
##    m_relax = relaxed_constants(m, None, ['M_{takeoff}', '\\theta_{db}'])
##
##    sol = m_relax.localsolve(verbosity=4, iteration_limit=200, reltol=0.01)
##    post_process(sol)
##
##    percent_diff(sol, 'b737800', Nclimb)
##
##    post_compute(sol, Nclimb)
##
##    return sol
##
##def run_M072_optimal_RJ(objective, fixedBPR, pRatOpt, mutategparg):
##    # User definitions
##    Nclimb = 3
##    Ncruise = 2
##    Nmission = 1
##    aircraft = 'optimalRJ'
##
##    m = Mission(Nclimb, Ncruise, objective, aircraft, Nmission)
##    
##    substitutions = get_M072_optimal_RJ_subs()
##
##    substitutions.update({
####        'n_{pass}': [90.],
##        'R_{req}': [1500.],
##    })
##
##    if fixedBPR:
##        substitutions.update({
##            '\\alpha_{max}': 5.6958, 
##        })
##
##    if pRatOpt:
##        del substitutions['\pi_{f_D}']
####        del substitutions['\pi_{lc_D}']
####        del substitutions['\pi_{hc_D}']
##
##    m.substitutions.update(substitutions)
##    m = Model(m.cost, BCS(m))
##    m_relax = relaxed_constants(m, None, ['M_{takeoff}', '\\theta_{db}'])
##
##    sol = m_relax.localsolve(verbosity=4, iteration_limit=200, reltol=0.01)
##    post_process(sol)
##
##    percent_diff(sol, 'b737800', Nclimb)
##
##    post_compute(sol, Nclimb)
##
##    return sol
##
##def run_small_D8(objective, fixedBPR, pRatOpt, mutategparg):
##    # User definitions
##    Nclimb = 3
##    Ncruise = 2
##    Nmission = 1
##    aircraft = 'smallD8'
##
##    m = Mission(Nclimb, Ncruise, objective, aircraft, Nmission)
##    
##    substitutions = get_small_D8_subs()
##
##    substitutions.update({
####        'n_{pass}': [90.],
##        'R_{req}': [1500.],
##    })
##
##    if fixedBPR:
##        substitutions.update({
##            '\\alpha_{max}': 5.6958, 
##        })
##
##    if pRatOpt:
##        del substitutions['\pi_{f_D}']
####        del substitutions['\pi_{lc_D}']
####        del substitutions['\pi_{hc_D}']
##
##    m.substitutions.update(substitutions)
##    m = Model(m.cost, BCS(m))
##    m_relax = relaxed_constants(m, None, ['M_{takeoff}', '\\theta_{db}'])
##
##    sol = m_relax.localsolve(verbosity=4, iteration_limit=200, reltol=0.01)
##    post_process(sol)
##
##    percent_diff(sol, 'b737800', Nclimb)
##
##    post_compute(sol, Nclimb)
##
##    return sol
##
##def run_small_M08_D8(objective, fixedBPR, pRatOpt, mutategparg):
##    # User definitions
##    Nclimb = 3
##    Ncruise = 2
##    Nmission = 1
##    aircraft = 'smallD8'
##
##    m = Mission(Nclimb, Ncruise, objective, aircraft, Nmission)
##    
##    substitutions = get_small_M08_D8_subs()
##
##    substitutions.update({
####        'n_{pass}': [90.],
##        'R_{req}': [1500.],
##    })
##
##    if fixedBPR:
##        substitutions.update({
##            '\\alpha_{max}': 5.6958, 
##        })
##
##    if pRatOpt:
##        del substitutions['\pi_{f_D}']
####        del substitutions['\pi_{lc_D}']
####        del substitutions['\pi_{hc_D}']
##
##    m.substitutions.update(substitutions)
##    m = Model(m.cost, BCS(m))
##    m_relax = relaxed_constants(m, None, ['M_{takeoff}', '\\theta_{db}'])
##
##    sol = m_relax.localsolve(verbosity=4, iteration_limit=200, reltol=0.01)
##    post_process(sol)
##
##    percent_diff(sol, 'b737800', Nclimb)
##
##    return sol
##
##def run_small_D8_eng_wing(objective, fixedBPR, pRatOpt, mutategparg):
##    # User definitions
##    Nclimb = 3
##    Ncruise = 2
##    Nmission = 1
##    aircraft = 'smallD8_eng_wing'
##
##    m = Mission(Nclimb, Ncruise, objective, aircraft, Nmission)
##    
##    substitutions = get_small_D8_eng_wing_subs()
##
##    substitutions.update({
####        'n_{pass}': [90.],
##        'R_{req}': [1500.],
##    })
##
##    if fixedBPR:
##        substitutions.update({
##            '\\alpha_{max}': 5.6958, 
##        })
##
##    if pRatOpt:
##        del substitutions['\pi_{f_D}']
####        del substitutions['\pi_{lc_D}']
####        del substitutions['\pi_{hc_D}']
##
##    m.substitutions.update(substitutions)
##    m = Model(m.cost, BCS(m))
##    m_relax = relaxed_constants(m, None, ['M_{takeoff}', '\\theta_{db}'])
##
##    sol = m_relax.localsolve(verbosity=4, iteration_limit=200, reltol=0.01)
##    post_process(sol)
##
##    percent_diff(sol, 'b737800', Nclimb)
##
##    post_compute(sol, Nclimb)
##
##    return sol
##
##def run_small_M08_D8_eng_wing(objective, fixedBPR, pRatOpt, mutategparg):
##    # User definitions
##    Nclimb = 3
##    Ncruise = 2
##    Nmission = 1
##    aircraft = 'smallD8_M08_eng_wing'
##
##    m = Mission(Nclimb, Ncruise, objective, aircraft, Nmission)
##    
##    substitutions = get_small_M08_D8_eng_wing_subs()
##
##    substitutions.update({
####        'n_{pass}': [90.],
##        'R_{req}': [1500.],
##    })
##
##    if fixedBPR:
##        substitutions.update({
##            '\\alpha_{max}': 5.6958, 
##        })
##
##    if pRatOpt:
##        del substitutions['\pi_{f_D}']
####        del substitutions['\pi_{lc_D}']
####        del substitutions['\pi_{hc_D}']
##
##    m.substitutions.update(substitutions)
##    m = Model(m.cost, BCS(m))
##    m_relax = relaxed_constants(m, None, ['M_{takeoff}', '\\theta_{db}'])
##
##    sol = m_relax.localsolve(verbosity=4, iteration_limit=200, reltol=0.01)
##    post_process(sol)
##
##    percent_diff(sol, 'b737800', Nclimb)
##
##    post_compute(sol, Nclimb)
##
##    return sol
##
##def run_small_D8_no_BLI(objective, fixedBPR, pRatOpt, mutategparg):
##    # User definitions
##    Nclimb = 3
##    Ncruise = 2
##    Nmission = 1
##    aircraft = 'smallD8_no_BLI'
##
##    m = Mission(Nclimb, Ncruise, objective, aircraft, Nmission)
##    
##    substitutions = get_small_D8_no_BLI_subs()
##
##    substitutions.update({
####        'n_{pass}': [90.],
##        'R_{req}': [1500.],
##    })
##
##    if fixedBPR:
##        substitutions.update({
##            '\\alpha_{max}': 5.6958, 
##        })
##
##    if pRatOpt:
##        del substitutions['\pi_{f_D}']
####        del substitutions['\pi_{lc_D}']
####        del substitutions['\pi_{hc_D}']
##
##    m.substitutions.update(substitutions)
##    m = Model(m.cost, BCS(m))
##    m_relax = relaxed_constants(m, None, ['M_{takeoff}', '\\theta_{db}'])
##
##    sol = m_relax.localsolve(verbosity=4, iteration_limit=200, reltol=0.01)
##    post_process(sol)
##
##    percent_diff(sol, 'b737800', Nclimb)
##
##    post_compute(sol, Nclimb)
##
##    return sol
##
##def run_small_M08_D8_no_BLI(objective, fixedBPR, pRatOpt, mutategparg):
##    # User definitions
##    Nclimb = 3
##    Ncruise = 2
##    Nmission = 1
##    aircraft = 'smallD8_M08_no_BLI'
##
##    m = Mission(Nclimb, Ncruise, objective, aircraft, Nmission)
##    
##    substitutions = get_small_M08_D8_no_BLI_subs()
##
##    substitutions.update({
####        'n_{pass}': [90.],
##        'R_{req}': [1500.],
##    })
##
##    if fixedBPR:
##        substitutions.update({
##            '\\alpha_{max}': 5.6958, 
##        })
##
##    if pRatOpt:
##        del substitutions['\pi_{f_D}']
####        del substitutions['\pi_{lc_D}']
####        del substitutions['\pi_{hc_D}']
##
##    m.substitutions.update(substitutions)
##    m = Model(m.cost, BCS(m))
##    m_relax = relaxed_constants(m, None, ['M_{takeoff}', '\\theta_{db}'])
##
##    sol = m_relax.localsolve(verbosity=4, iteration_limit=200, reltol=0.01)
##    post_process(sol)
##
##    percent_diff(sol, 'b737800', Nclimb)
##
##    post_compute(sol, Nclimb)
##
##    return sol
