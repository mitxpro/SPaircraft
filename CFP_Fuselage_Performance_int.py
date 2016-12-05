"""Simple commercial aircraft flight profile and aircraft model"""
""" Combines Wing and Fuselage models for D8"""
from numpy import pi, cos, tan
import numpy as np
from gpkit import Variable, Model, units, SignomialsEnabled, SignomialEquality, Vectorize
from gpkit.tools import te_exp_minus1
from gpkit.constraints.tight import Tight as TCS
from gpkit.constraints.bounded import Bounded as BCS

# only needed for the local bounded debugging tool
from collections import defaultdict
from gpkit.small_scripts import mag

# importing from D8_integration
from stand_alone_simple_profile import FlightState, Altitude, Atmosphere
from D8_VT_yaw_rate_and_EO_simple_profile import VerticalTail, VerticalTailPerformance
from D8_HT_simple_profile import HorizontalTail, HorizontalTailPerformance
from Wing_simple_performance import Wing, WingPerformance
from D8_integration import Engine, EnginePerformance

sweep = 30

"""
Models requird to minimize the aircraft total fuel weight. Rate of climb equation taken from John
Anderson's Aircraft Performance and Design (eqn 5.85).

Inputs
-----

- Number of passengers
- Passenger weight [N]
- Fuselage area per passenger (recommended to use 1 m^2 based on research) [m^2]
- Engine weight [N]
- Number of engines
- Required mission range [nm]
- Oswald efficiency factor
- Max allowed wing span [m]
- Cruise altitude [ft]

Sources for substitutions:
-[b757 freight doc]
-[Boeing]
-[Philippe]
-[stdAtm]
-[TAS]

Other markers:
-[SP]
-[SPEquality]
"""

g = 9.81 * units('m*s**-2')


class Aircraft(Model):
    "Aircraft class"

    def setup(self, **kwargs):
        # create submodels
        self.fuse = Fuselage()
        self.wing = Wing()
        self.engine = Engine()
        self.VT = VerticalTail()
        self.HT = HorizontalTail()

        # variable definitions
        numeng = Variable('numeng', '-', 'Number of Engines')

        constraints = []

        with SignomialsEnabled():
            constraints.extend([numeng == numeng,
                            # substitutions with replicated variable names
                            self.wing['c_{root}'] == self.fuse['c_0'],
                            self.wing.wb['wwb'] == self.fuse['wtc'],
                            self.wing['V_{ne}'] == 144*units('m/s'),
                            self.fuse['V_{NE}'] == 144*units('m/s'),
                            self.VT['V_{ne}'] == 144*units('m/s'),
                            self.HT['\\rho_0'] == 1.225*units('kg/m^3'),
                            self.wing['\\rho_0'] == 1.225*units('kg/m^3'),

                            # self.HT['V_{ne}'] == 144*units('m/s'),
                            # self.wing['b'] <= 35*units('m'),
                            # self.wing['\\bar{c}_w'] >= 1*units('m'),
                            # self.wing['y_{\\bar{c}_w}'] == 5.675*units('m'),
                            # self.wing.wb['\bar{A}_{fuel, max}'] == 0.069,

                            # Tail cone sizing
                            3 * self.VT['M_r'] * self.VT['c_{root_{vt}}'] * \
                                (self.fuse['p_{\\lambda_v}'] - 1) >= self.VT[
                                    'L_{v_{max}}'] * self.VT['b_{vt}'] * (self.fuse['p_{\\lambda_v}']), 
                            # TCS([Vcone * (1 + lamcone) * (pi + 4 * thetadb) >= self.VT[
                            #     'M_r'] / taucone * (pi + 2 * thetadb) * (lcone / Rfuse) * 2]),
                            TCS([self.fuse['V_{cone}'] * (1 + self.fuse['\\lambda_{cone}']) * \
                             (pi + 4 * self.fuse['\\theta_{db}']) >= 2*self.VT[
                                'M_r'] * self.VT['c_{root_{vt}}'] / self.fuse['\\tau_{cone}'] * \
                                 (pi + 2 * self.fuse['\\theta_{db}']) * \
                                  (self.fuse['l_{cone}'] / self.fuse['R_{fuse}'])]), #[SP]
                
                            # Tail weight
                            self.fuse['W_{tail}'] >= 2*self.VT['W_{struct}'] + \
                                self.HT['W_{struct}'] + self.fuse['W_{cone}'],

                            # Fuselage bending mat'l sizing - Aero loads constant A1h
                            self.fuse['A1h'] >= (self.fuse['N_{land}'] * self.fuse['W_{tail}'] \
                                + self.fuse['r_{M_h}'] * self.HT['L_{{max}_h}']) / \
                                 (self.fuse['h_{fuse}'] * self.fuse['\\sigma_{M_h}']),

                            # Horizontal tail sizing
                            # Horizontal tail volume coefficient
                            self.HT['V_{h}'] == self.HT['S_h']*self.HT['x_{CG_{ht}}']/(self.wing['S']*self.wing['\\bar{c}_w']),
                            # Horizontal tail maximum load
                            self.HT['L_{{max}_h}'] == 0.5*self.HT['\\rho_0']*self.wing['V_{ne}']**2*self.HT['S_h']*self.HT['C_{L_{hmax}}'],
                            # Wing-to-tail lift slope ratio m_ratio
                            SignomialEquality(self.HT['m_{ratio}']*(1+2/self.wing['AR']), 1 + 2/self.HT['AR_h']), #[SPEquality]

                            # Enforce max tail location is the end of the fuselage
                            self.HT['x_{CG_{ht}}'] <= self.fuse['l_{fuse}'],

                            # Compute the HT chord at its attachment point to the VT
                            (self.HT['b_{ht}']/self.fuse['w_{fuse}'])*self.HT['\lambda_h']* \
                            self.HT['c_{root_h}'] == self.HT['c_{attach}'],

                            ])

        self.components = [self.fuse, self.wing, self.engine, self.VT, self.HT]

        return self.components, constraints

    def climb_dynamic(self, state):
        """
        creates an aircraft climb performance model, given a state
        """
        return ClimbP(self, state)

    def cruise_dynamic(self, state):
        """
        creates an aircraft cruise performance model, given a state
        """
        return CruiseP(self, state)


class AircraftP(Model):
    """
    aircraft performance models superclass, contains constraints true for
    all flight segments
    """

    def setup(self, aircraft, state):
        # make submodels
        self.aircraft = aircraft
        self.wingP = aircraft.wing.dynamic(state)
        self.fuseP = aircraft.fuse.dynamic(state)
        self.engineP = aircraft.engine.dynamic(state)
        self.VTP = aircraft.VT.dynamic(aircraft.fuse,state)
        self.HTP = aircraft.HT.dynamic(aircraft.fuse,aircraft.wing,state)
        self.Pmodels = [self.wingP, self.fuseP, self.engineP, self.VTP, self.HTP]

        # variable definitions
        Vstall = Variable('V_{stall}', 'knots', 'Aircraft Stall Speed')
        D = Variable('D', 'N', 'Total Aircraft Drag')
        W_avg = Variable(
            'W_{avg}', 'N', 'Geometric Average of Segment Start and End Weight')
        W_start = Variable('W_{start}', 'N', 'Segment Start Weight')
        W_end = Variable('W_{end}', 'N', 'Segment End Weight')
        W_burn = Variable('W_{burn}', 'N', 'Segment Fuel Burn Weight')
        WLoadmax = Variable('W_{Load_max}', 'N/m^2', 'Max Wing Loading')
        WLoad = Variable('W_{Load}', 'N/m^2', 'Wing Loading')
        t = Variable('tmin', 'min', 'Segment Flight Time in Minutes')
        thours = Variable('thr', 'hour', 'Segment Flight Time in Hours')

        xCG = Variable('x_{CG}','m','x-location of the CG')

        constraints = []

        constraints.extend([
            # speed must be greater than stall speed
            state['V'] >= Vstall,


            # Figure out how to delete
            Vstall == 120 * units('kts'),
            WLoadmax == 6664 * units('N/m^2'),

            # Compute the drag
            TCS([D >= self.wingP['D_{wing}'] + self.fuseP['D_{fuse}'] + self.VTP['D_{vt}'] + self.HTP['D_{ht}']]),

            # Constrain CL and compute the wing loading
            W_avg == .5 * self.wingP['C_{L}'] * self.aircraft['S'] * \
            state.atm['\\rho'] * state['V']**2,
            WLoad == .5 * self.wingP['C_{L}'] * self.aircraft['S'] * \
            state.atm['\\rho'] * state['V']**2 / self.aircraft.wing['S'],

            # set average weight equal to the geometric avg of start and end
            # weight
            W_avg == (W_start * W_end)**.5,

            # constrain the max wing loading
            WLoad <= WLoadmax,

            # compute fuel burn from TSFC
            W_burn == aircraft['numeng'] * self.engineP['TSFC'] * \
            thours * self.engineP['thrust'],

            # time unit conversion
            t == thours,

            #TODO CG placeholder
            xCG == 0.65*self.aircraft.fuse['l_{fuse}'],  # temporary CG substitution #TODO

            # Wing location constraint
            # aircraft.wing['x_w'] == aircraft.fuse['x_{wing}'],

            #VTP constraints
            aircraft.fuse['l_{fuse}'] >= aircraft.VT['\\Delta x_{lead_v}'] + xCG,
            aircraft.VT['x_{CG_{vt}}'] >= xCG +(aircraft.VT['\\Delta x_{lead_v}']+aircraft.VT['\\Delta x_{trail_v}'])/2,

            ])
        with SignomialsEnabled():
            constraints.extend([

            # Static margin constraint
            TCS([aircraft.HT['SM_{min}'] + aircraft.HT['\\Delta x_{CG}']/aircraft.wing['\\bar{c}_w'] <=  \
                aircraft.HT['V_{h}']*aircraft.HT['m_{ratio}'] + self.wingP['c_{m_{w}}']/aircraft.wing['C_{L_{wmax}}'] + \
                    aircraft.HT['V_{h}']*aircraft.HT['C_{L_{hmax}}']/aircraft.wing['C_{L_{wmax}}']]), #[SP]
            ])       
        

        return self.Pmodels, constraints


class ClimbP(Model):
    """
    Climb constraints
    """

    def setup(self, aircraft, state, **kwargs):
        # submodels
        self.aircraft = aircraft
        self.aircraftP = AircraftP(aircraft, state)
        self.wingP = self.aircraftP.wingP
        self.fuseP = self.aircraftP.fuseP
        self.engineP = self.aircraftP.engineP

        # variable definitions
        theta = Variable('\\theta', '-', 'Aircraft Climb Angle')
        excessP = Variable('excessP', 'W', 'Excess Power During Climb')
        RC = Variable('RC', 'feet/min', 'Rate of Climb/Decent')
        dhft = Variable(
            'dhft', 'feet', 'Change in Altitude Per Climb Segment [feet]')
        RngClimb = Variable('RngClimb', 'nautical_miles',
                            'Down Range Covered in Each Climb Segment')

        # constraints
        constraints = []

        constraints.extend([
            # constraint on drag and thrust
            self.aircraft['numeng'] * self.engineP['thrust'] >= self.aircraftP[
                'D'] + self.aircraftP['W_{avg}'] * theta,

            # climb rate constraints
            TCS([excessP + state['V'] * self.aircraftP['D'] <= state['V']
                 * aircraft['numeng'] * self.engineP['thrust']]),

            RC == excessP / self.aircraftP['W_{avg}'],
            RC >= 500 * units('ft/min'),

            # make the small angle approximation and compute theta
            theta * state['V'] == RC,

            dhft == self.aircraftP['tmin'] * RC,

            # makes a small angle assumption during climb
            RngClimb == self.aircraftP['thr'] * state['V'],

            # Setting rho_0s #TODO REMOVE
            # self.wingP['\\rho_0'] == 1.225*units('kg/m^3'),
        ])

        return constraints + self.aircraftP


class CruiseP(Model):
    """
    Cruise constraints
    """

    def setup(self, aircraft, state, **kwargs):
        self.aircraft = aircraft
        self.aircraftP = AircraftP(aircraft, state)
        self.wingP = self.aircraftP.wingP
        self.fuseP = self.aircraftP.fuseP
        self.engineP = self.aircraftP.engineP

        # variable definitions
        z_bre = Variable('z_{bre}', '-', 'Breguet Parameter')
        Rng = Variable('Rng', 'nautical_miles', 'Cruise Segment Range')

        constraints = []

        constraints.extend([
            # Steady level flight constraint on D
            self.aircraftP['D'] == aircraft[
                'numeng'] * self.engineP['thrust'],

            # Taylor series expansion to get the weight term
            TCS([self.aircraftP['W_{burn}'] / self.aircraftP['W_{end}'] >=
                 te_exp_minus1(z_bre, nterm=3)]),

            # Breguet range eqn
            TCS([z_bre >= (self.engineP['TSFC'] * self.aircraftP['thr'] *
                           self.aircraftP['D']) / self.aircraftP['W_{avg}']]),

            # Time
            self.aircraftP['thr'] * state['V'] == Rng,
        ])

        return constraints + self.aircraftP


class CruiseSegment(Model):
    """
    Combines a flight state and aircrat to form a cruise flight segment
    """

    def setup(self, aircraft, **kwargs):
        self.state = FlightState()
        self.cruiseP = aircraft.cruise_dynamic(self.state)

        return self.state, self.cruiseP


class ClimbSegment(Model):
    """
    Combines a flight state and aircrat to form a cruise flight segment
    """

    def setup(self, aircraft, **kwargs):
        self.state = FlightState()
        self.climbP = aircraft.climb_dynamic(self.state)

        return self.state, self.climbP

class HTail(Model):

    def dynamic(self, state):
        return HTailP(self, state)

    def setup(self, **kwargs):
        Whtail = Variable('W_{htail}', 10000, 'N',
                          'Horizontal tail weight')  # Temporarily
        Lhmax = Variable('L_{h_{max}}', 35000, 'N', 'Max horizontal tail load')
        Shtail = Variable('S_{htail}', 32 * 0.8, 'm^2',
                          'Horizontal tail area')  # Temporarily
        CLhmax = Variable('C_{L_{h_{max}}}', 2.5, '-',
                          'Max lift coefficient')  # Temporarily
        constraints = [] 

        return constraints

# class VTail(Model):

#     def dynamic(self, state):
#         return VTailP(self, state)

#     def setup(self, **kwargs):
#         bvt = Variable('b_{vt}', 7, 'm', 'Vertical tail span')
#         Lvmax = Variable('L_{v_{max}}', 35000, 'N', 'Max vertical tail load')
#         Wvtail = Variable('W_{vtail}', 10000, 'N',
#                           'Vertical tail weight')  # Temporarily
#         Qv = Variable('Q_v', 'N*m', 'Torsion moment imparted by tail')

#         constraints = []

#         return constraints

class Fuselage(Model):

    def setup(self, **kwargs):
        g = Variable('g',9.81,'m*s^-2','Acceleration due to gravity')
        # g = 9.81*units('m*s^-2')
        dPover = Variable('\\delta_P_{over}', 'psi', 'Cabin overpressure')
        npax = Variable('n_{pax}', '-', 'Number of Passengers to Carry')
        Nland = Variable('N_{land}', 6.0, '-',
                         'Emergency landing load factor')  # [TAS]
        VNE = Variable('V_{NE}',144, 'm/s', 'Never-exceed speed')  # [Philippe]
        SPR = Variable('SPR', '-', 'Number of seats per row')
        nrows = Variable('n_{rows}', '-', 'Number of rows')
        nseat = Variable('n_{seat}', '-', 'Number of seats')
        pitch = Variable('p_s', 'cm', 'Seat pitch')

        # Cross-sectional variables
        Adb = Variable('A_{db}', 'm^2', 'Web cross sectional area')
        Afloor = Variable('A_{floor}', 'm^2', 'Floor beam x-sectional area')
        Afuse = Variable('A_{fuse}', 'm^2', 'Fuselage x-sectional area')
        Askin = Variable('A_{skin}', 'm^2', 'Skin cross sectional area')
        hdb = Variable('h_{db}', 'm', 'Web half-height')
        hfloor = Variable('h_{floor}', 'm', 'Floor beam height')
        hfuse = Variable('h_{fuse}', 'm', 'Fuselage height')
        # will assume for now there: no under-fuselage extension deltaR
        Rfuse = Variable('R_{fuse}', 'm', 'Fuselage radius')
        tdb = Variable('t_{db}', 'm', 'Web thickness')
        thetadb = Variable('\\theta_{db}', '-', 'DB fuselage joining angle')
        tshell = Variable('t_{shell}', 'm', 'Shell thickness')
        tskin = Variable('t_{skin}', 'm', 'Skin thickness')
        waisle = Variable('w_{aisle}', 'm', 'Aisle width')  # [Boeing]
        wdb = Variable('w_{db}', 'm', 'DB added half-width')
        wfloor = Variable('w_{floor}', 'm', 'Floor half-width')
        wfuse = Variable('w_{fuse}', 'm', 'Fuselage width')
        wseat = Variable('w_{seat}', 'm', 'Seat width')  # [Philippe]
        wsys = Variable('w_{sys}', 'm', 'Width between cabin and skin for systems')  # [Philippe]

        # Tail cone variables
        lamcone = Variable(
            '\\lambda_{cone}', '-', 'Tailcone radius taper ratio (xshell2->xtail)')
        lcone = Variable('l_{cone}', 'm', 'Cone length')
        plamv = Variable('p_{\\lambda_v}', 1.5, '-', '1 + 2*Tail taper ratio')
        tcone = Variable('t_{cone}', 'm', 'Cone thickness')

        # Lengths (free)
        c0 = Variable('c_0', 'm', 'Root chord of the wing')
        lfuse = Variable('l_{fuse}', 'm', 'Fuselage length')
        lnose = Variable('l_{nose}', 'm', 'Nose length')
        lshell = Variable('l_{shell}', 'm', 'Shell length')
        lfloor = Variable('l_{floor}', 'm', 'Floor length')

        # Surface areas (free)
        Sbulk = Variable('S_{bulk}', 'm^2', 'Bulkhead surface area')
        Snose = Variable('S_{nose}', 'm^2', 'Nose surface area')

        # Volumes (free)
        Vbulk = Variable('V_{bulk}', 'm^3', 'Bulkhead skin volume')
        Vcabin = Variable('V_{cabin}', 'm^3', 'Cabin volume')
        Vcone = Variable('V_{cone}', 'm^3', 'Cone skin volume')
        Vcyl = Variable('V_{cyl}', 'm^3', 'Cylinder skin volume')
        Vdb = Variable('V_{db}', 'm^3', 'Web volume')
        Vfloor = Variable('V_{floor}', 'm^3', 'Floor volume')
        Vnose = Variable('V_{nose}', 'm^3', 'Nose skin volume')

        # Loads
        sigfloor = Variable(
            '\\sigma_{floor}', 30000 / 0.000145, 'N/m^2', 'Max allowable floor stress')  # [TAS]
        sigskin = Variable(
            '\\sigma_{skin}', 15000 / 0.000145, 'N/m^2', 'Max allowable skin stress')  # [TAS]
        sigth = Variable('\\sigma_{\\theta}', 'N/m^2', 'Skin hoop stress')
        sigx = Variable('\\sigma_x', 'N/m^2', 'Axial stress in skin')

        # Floor loads
        Mfloor = Variable('M_{floor}', 'N*m',
                          'Max bending moment in floor beams')
        Pfloor = Variable('P_{floor}', 'N', 'Distributed floor load')
        Sfloor = Variable('S_{floor}', 'N', 'Maximum shear in floor beams')
        sigfloor = Variable(
            '\\sigma_{floor}', 30000 / 0.000145, 'N/m^2', 'Max allowable floor stress')  # [TAS]
        taucone = Variable('\\tau_{cone}', 'N/m^2', 'Shear stress in cone')
        taufloor = Variable('\\tau_{floor}', 30000 / 0.000145,
                            'N/m^2', 'Max allowable shear web stress')  # [TAS]

        # Bending inertias (ported from TASOPT)
        # (shell inertia contribution)
        A0h = Variable('A0h', 'm^2', 'Horizontal bending area constant A0h')
        # (tail impact + aero loading)
        A1h = Variable('A1h', 'm', 'Horizontal bending area constant A1h')
        # (fuselage impact)
        A2h = Variable('A2h', '-', 'Horizontal bending area constant A2h')
        Ahbendb = Variable('A_{hbendb}', 'm^2',
                           'Horizontal bending area at rear wingbox')
        Ahbendf = Variable('A_{hbendf}', 'm^2',
                           'Horizontal bending area at front wingbox')
        Avbendb = Variable('A_{vbendb}', 'm^2',
                           'Vertical bending material area at rear wingbox')
        # B0           = Variable('B0','m^2','Vertical bending area constant B0') #(shell inertia contribution)
        # B1           = Variable('B1','m','Vertical bending area constant B1')
        # #(vertical tail bending load)
        Ihshell = Variable('I_{hshell}', 'm^4',
                           'Shell horizontal bending inertia')
        #Ivshell      = Variable('I_{vshell}','m^4','Shell vertical bending inertia')
        rMh = Variable('r_{M_h}', .4, '-',
                       'Horizontal inertial relief factor')  # [TAS]
        rMv = Variable('r_{M_v}', .7, '-',
                       'Vertical inertial relief factor')  # [TAS]
        sigbend = Variable('\\sigma_{bend}', 'N/m^2',
                           'Bending material stress')
        sigMh = Variable('\\sigma_{M_h}', 'N/m^2',
                         'Horizontal bending material stress')
        #sigMv        = Variable('\\sigma_{M_v}','N/m^2','Vertical bending material stress')
        Vhbend = Variable('V_{hbend}', 'm^3',
                          'Horizontal bending material volume')
        Vhbendb = Variable(
            'V_{hbendb}', 'm^3', 'Horizontal bending material volume b')  # back fuselage
        # center fuselage
        Vhbendc = Variable('V_{hbendc}', 'm^3',
                           'Horizontal bending material volume c')
        # front fuselage
        Vhbendf = Variable('V_{hbendf}', 'm^3',
                           'Horizontal bending material volume f')
        #Vvbend       = Variable('V_{vbend}','m^3','Vertical bending material volume')
        # Vvbendb      = Variable('V_{vbendb}','m^3','Vertical bending material volume b') #back fuselage
        # Vvbendc      = Variable('V_{vbendc}','m^3','Vertical bending material
        # volume c') #center fuselage
        Whbend = Variable('W_{hbend}', 'lbf',
                          'Horizontal bending material weight')
        #Wvbend       = Variable('W_{vbend}','N','Vertical bending material weight')
        xhbend = Variable('x_{hbend}', 'm', 'Horizontal zero bending location')
        #xvbend       = Variable('x_{vbend}','m','Vertical zero bending location')

        # Material properties
        rE = Variable('r_E', 1., '-', 'Ratio of stringer/skin moduli')  # [TAS]
        # [b757 freight doc]
        rhocargo = Variable('\\rho_{cargo}', 150, 'kg/m^3', 'Cargo density')
        rhocone = Variable('\\rho_{cone}', 'kg/m^3',
                           'Cone material density')  # [TAS]
        rhobend = Variable('\\rho_{bend}', 'kg/m^3',
                           'Stringer density')  # [TAS]
        rhofloor = Variable('\\rho_{floor}', 'kg/m^3',
                            'Floor material density')  # [TAS]
        rholugg = Variable('\\rho_{lugg}', 100,
                           'kg/m^3', 'Luggage density')  # [Philippe]
        rhoskin = Variable('\\rho_{skin}', 'kg/m^3', 'Skin density')  # [TAS]
        Wppfloor = Variable('W\'\'_{floor}', 'N/m^2',
                            'Floor weight/area density')  # [TAS]
        Wppinsul = Variable(
            'W\'\'_{insul}', 'N/m^2', 'Weight/area density of insulation material')  # [TAS]
        Wpseat = Variable('W\'_{seat}', 'N', 'Weight per seat')  # [TAS]
        Wpwindow = Variable('W\'_{window}', 'N/m',
                            'Weight/length density of windows')  # [TAS]

        # Weight fractions
        fapu = Variable('f_{apu}', 0.035, '-',
                        'APU weight as fraction of payload weight')  # [TAS]
        ffadd = Variable(
            'f_{fadd}', '-', 'Fractional added weight of local reinforcements')  # [TAS]
        fframe = Variable('f_{frame}', '-',
                          'Fractional frame weight')  # [Philippe]
        flugg1 = Variable(
            'f_{lugg,1}', '-', 'Proportion of passengers with one suitcase')  # [Philippe]
        flugg2 = Variable(
            'f_{lugg,2}', '-', 'Proportion of passengers with two suitcases')  # [Philippe]
        fpadd = Variable('f_{padd}', 0.4, '-',
                         'Other misc weight as fraction of payload weight')
        fstring = Variable('f_{string}', '-',
                           'Fractional stringer weight')  # [Philippe]

        # Weights
        Wapu = Variable('W_{apu}', 'lbf', 'APU weight')
        Wavgpass = Variable('W_{avg. pass}', 'lbf',
                            'Average passenger weight')  # [Philippe]
        Wcargo = Variable('W_{cargo}', 'N', 'Cargo weight')  # [Philippe]
        Wcarryon = Variable('W_{carry on}', 'lbf',
                            'Ave. carry-on weight')  # [Philippe]
        Wchecked = Variable('W_{checked}', 'lbf',
                            'Ave. checked bag weight')  # [Philippe]
        Wcone = Variable('W_{cone}', 'lbf', 'Cone weight')
        Wdb = Variable('W_{db}', 'N', 'Web weight')
        Wfix = Variable(
            'W_{fix}', 3000, 'lbf', 'Fixed weights (pilots, cockpit seats, navcom)')  # [Philippe]
        Wfloor = Variable('W_{floor}', 'lbf', 'Floor weight')
        Wfuse = Variable('W_{fuse}', 'lbf', 'Fuselage weight')
        Winsul = Variable('W_{insul}', 'lbf', 'Insulation material weight')
        Wlugg = Variable('W_{lugg}', 'N', 'Passenger luggage weight')
        Wpadd = Variable('W_{padd}', 'lbf',
                         'Misc weights (galley, toilets, doors etc.)')
        Wpax = Variable('W_{pax}', 'N', 'Passenger weight')
        Wpay = Variable('W_{payload}', 'N', 'Payload weight')
        Wseat = Variable('W_{seat}', 'lbf', 'Seating weight')
        Wshell = Variable('W_{shell}', 'N', 'Shell weight')
        Wskin = Variable('W_{skin}', 'N', 'Skin weight')
        Wtail = Variable('W_{tail}', 'lbf', 'Total tail weight')
        Wwindow = Variable('W_{window}', 'lbf', 'Window weight')

        # x-location variables
        xshell1 = Variable('x_{shell1}', 'm', 'Start of cylinder section')
        xshell2 = Variable('x_{shell2}', 'm', 'End of cylinder section')
        xtail = Variable('x_{tail}', 'm', 'x-location of tail')
        xwing = Variable('x_{wing}', 'm', 'x-location of wing')

        # Wingbox variables
        xf = Variable('x_f', 'm', 'x-location of front of wingbox')
        xb = Variable('x_b', 'm', 'x-location of back of wingbox')
        w = Variable('wtc', 0.5, '-', 'Wingbox-width-to-chord ratio')

        constraints = []
        with SignomialsEnabled():
            constraints.extend([
                Nland == Nland,
                VNE == VNE,
                plamv == plamv,

                # Passenger constraints
                Wlugg >= flugg2 * npax * 2 * Wchecked + flugg1 * npax * Wchecked + Wcarryon,
                Wpax == npax * Wavgpass,
                Wpay >= Wpax + Wlugg + Wcargo,
                nseat == npax,
                nrows == nseat / SPR,
                lshell == nrows * pitch,

                # Fuselage joint angle relations
                thetadb == wdb / Rfuse,  # first order Taylor works...
                # thetadb >= 0.05, thetadb <= 0.5,  # Temporarily
                thetadb == 0.366,
                hdb >= Rfuse * (1.0 - .5 * thetadb**2),  # [SP]

                # Cross-sectional constraints
                Adb == (2 * hdb) * tdb,
                Afuse >= (pi + 2 * thetadb + 2 * thetadb * \
                          (1 - thetadb**2 / 2)) * Rfuse**2,  # [SP]
                # Afuse       >= (pi + 4*thetadb)*Rfuse**2, #Bad approx, should
                # improve
                Askin >= (2 * pi + 4 * thetadb) * Rfuse * \
                tskin + Adb,  # no delta R for now
                wfloor == .5 * wfuse,
                TCS([wfuse >= SPR * wseat + 2 * waisle + 2 * wsys + tdb]),
                wfuse <= 2 * (Rfuse + wdb),
                hfuse == Rfuse,
                TCS([tshell <= tskin * (1. + rE * fstring * rhoskin / rhobend)]), #[SP]

                # Fuselage surface area relations
                Snose >= (2 * pi + 4 * thetadb) * Rfuse**2 * \
                (1 / 3 + 2 / 3 * (lnose / Rfuse)**(8 / 5))**(5 / 8),
                Sbulk >= (2 * pi + 4 * thetadb) * Rfuse**2,

                # Fuselage length relations
                SignomialEquality(lfuse, lnose + lshell + lcone), #[SPEquality] 
                lnose == 0.3 * lshell,  # Temporarily
                lcone == Rfuse / lamcone,
                xshell1 == lnose,
                TCS([xshell2 >= lnose + lshell]), 
                # STRESS RELATIONS
                # Pressure shell loading
                tskin == dPover * Rfuse / sigskin,
                tdb == 2 * dPover * wdb / sigskin,
                sigx == dPover * Rfuse / (2 * tshell),
                sigth == dPover * Rfuse / tskin,

                # Floor loading
                lfloor >= lshell + 2 * Rfuse,
                Pfloor >= Nland * (Wpay + Wseat),
                Mfloor == 9. / 256. * Pfloor * wfloor,
                Afloor >= 2. * Mfloor / (sigfloor * hfloor) + 1.5 * Sfloor / taufloor,
                Vfloor == 2 * wfloor * Afloor,
                Wfloor >= rhofloor * g * Vfloor + 2 * wfloor * lfloor * Wppfloor,
                Sfloor == (5. / 16.) * Pfloor,
                hfloor <= 0.1 * Rfuse,

                # Tail cone sizing
                taucone == sigskin,
                Wcone >= rhocone * g * Vcone * (1 + fstring + fframe),
                TCS([xtail >= lnose + lshell + .5 * lcone]),  # Temporarily
                
                # Horizontal bending model
                # Maximum axial stress is the sum of bending and pressurization
                # stresses
                Ihshell <= ((pi + 4 * thetadb) * Rfuse**2) * \
                Rfuse * tshell + 2 / 3 * hdb**3 * tdb,  # [SP]
                # Ivshell <= (pi*Rfuse**2 + 8*wdb*Rfuse +
                # (2*pi+4*thetadb)*wdb**2)*Rfuse*tshell, #[SP] #Ivshell
                # approximation needs to be improved
                sigbend == rE * sigskin,

                # Horizontal bending material model
                # Calculating xbend, the location where additional bending
                # material is required
                xhbend >= xwing,
                # [SP] #[SPEquality]
                SignomialEquality(A0h, A2h * (xshell2 - xhbend) ** 2 + A1h * (xtail - xhbend)),
                A2h >= Nland * (Wpay + Wshell + Wwindow + Winsul + Wfloor + Wseat) / \
                (2 * lshell * hfuse * sigMh),  # Landing loads constant A2h #[SPEquality]
                # Shell inertia constant A0h
                A0h == (Ihshell / (rE * hfuse**2)),
                # [SP]  # Bending area forward of wingbox
                Ahbendf >= A2h * (xshell2 - xf)**2 + A1h * (xtail - xf) - A0h,
                # [SP]  # Bending area behind wingbox
                Ahbendb >= A2h * (xshell2 - xb)**2 + A1h * (xtail - xb) - A0h, # [SP]

                Vhbendf >= A2h / 3 * ((xshell2 - xf)**3 - (xshell2 - xhbend)**3) \
                + A1h / 2 * ((xtail - xf)**2 - (xtail - xhbend)**2) \
                + A0h * (xhbend - xf),  # [SP]

                Vhbendb >= A2h / 3 * ((xshell2 - xb)**3 - (xshell2 - xhbend)**3) \
                + A1h / 2 * ((xtail - xb)**2 - (xtail - xhbend)**2) \
                + A0h * (xhbend - xb),  # [SP]
                Vhbendc >= .5 * (Ahbendf + Ahbendb) * c0 * w,
                Vhbend >= Vhbendc + Vhbendf + Vhbendb,
                Whbend >= g * rhobend * Vhbend,

                # Wing variable substitutions
                SignomialEquality(xf, xwing + .5 * c0 * \
                                  w),  # [SP] [SPEquality]
                SignomialEquality(xb, xwing - .5 * c0 * \
                                  w),  # [SP] [SPEquality]

                sigMh <= sigbend - rE * dPover / 2 * Rfuse / tshell,
                SignomialEquality(xwing, lnose + 0.6 * lshell),  #[SPEquality] #TODO


                # Volume relations
                Vcyl == Askin * lshell,
                Vnose == Snose * tskin,
                Vbulk == Sbulk * tskin,
                Vdb == Adb * lshell,
                # TODO Revert to posynomial after debugging
                # [SP] #[SPEquality]
                SignomialEquality(Vcabin, Afuse * (lshell + 0.67 * lnose + 0.67 * Rfuse)),

                # Weight relations
                Wapu == Wpay * fapu,
                Wdb == rhoskin * g * Vdb,
                Winsul >= Wppinsul * \
                ((1.1 * pi + 2 * thetadb) * Rfuse * \
                 lshell + 0.55 * (Snose + Sbulk)),
                Wlugg >= flugg2 * npax * 2 * Wchecked + flugg1 * npax * Wchecked + Wcarryon,
                Wwindow >= Wpwindow * lshell,
                Wpadd == Wpay * fpadd,
                Wseat == Wpseat * nseat,

                Wskin >= rhoskin * g * (Vcyl + Vnose + Vbulk),
                # + Whbend, #+ Wvbend,
                Wshell >= Wskin * (1 + fstring + ffadd + fframe) + Wdb,
                Wfuse >= Wshell + Wfloor + Wtail + Winsul + \
                Wapu + Wfix + Wwindow + Wpadd + Wseat + Whbend,

            ])

        return constraints

    def dynamic(self, state):
        """
        returns a fuselage performance model
        """
        return FuselagePerformance(self, state)


class FuselagePerformance(Model):
    """
    Fuselage performance model
    """

    def setup(self, fuse, state, **kwargs):
        Cdfuse = Variable('C_{D_{fuse}}', '-', 'Fuselage Drag Coefficient')
        Dfuse = Variable('D_{fuse}', 'N', 'Total drag in cruise')
        Dfrict = Variable('D_{friction}', 'N', 'Friction drag')
        Dupswp = Variable('D_{upsweep}', 'N', 'Drag due to fuse upsweep')
        f = Variable('f', '-', 'Fineness ratio')
        FF = Variable('FF', '-', 'Fuselage form factor')
        phi = Variable('\\phi', '-', 'Upsweep angle')

        constraints = []
        constraints.extend([
            #Dfuse == Cdfuse * (.5 * fuse['A_{fuse}'] * state.atm['\\rho'] * state['V']**2),
            # Fineness ratio
            f == fuse['l_{fuse}'] / ((4 / np.pi * fuse['A_{fuse}'])**0.5),
            FF >= 1 + 60 / f**3 + f / 400,  # form factor
            Dfrict >= FF * np.pi * fuse['R_{fuse}'] * state.atm['\\mu'] * state['V'] * 0.074 * (state.atm['\\rho'] * state['V']
                                                                                                * fuse['l_{fuse}'] / state.atm['\\mu'])**0.8,
            # Monomial fit of tan(phi)
            1.13226 * phi**1.03759 == fuse['R_{fuse}'] / fuse['l_{cone}'],
            Dupswp >= 3.83 * phi**2.5 * \
            fuse['A_{fuse}'] * 0.5 * state.atm['\\rho'] * state['V']**2,
            Dfuse >= Dfrict + Dupswp,
            Dfuse == 0.5 * state.atm['\\rho'] * \
            state['V']**2 * Cdfuse * fuse['A_{fuse}'],

        ])

        return constraints


class Mission(Model):
    """
    mission class, links together all subclasses
    """

    def setup(self, **kwargs):
        # define the number of each flight segment
        Nclimb = 2
        Ncruise = 2

        # build required submodels
        aircraft = Aircraft()

        # vectorize
        with Vectorize(Nclimb):
            cls = ClimbSegment(aircraft)

        with Vectorize(Ncruise):
            crs = CruiseSegment(aircraft)

        # declare new variables
        W_ftotal = Variable('W_{f_{total}}', 'N', 'Total Fuel Weight')
        W_fclimb = Variable('W_{f_{climb}}', 'N',
                            'Fuel Weight Burned in Climb')
        W_fcruise = Variable('W_{f_{cruise}}', 'N',
                             'Fuel Weight Burned in Cruise')
        W_total = Variable('W_{total}', 'N', 'Total Aircraft Weight')
        CruiseAlt = Variable('CruiseAlt', 'ft', 'Cruise Altitude [feet]')
        ReqRng = Variable('ReqRng', 'nautical_miles', 'Required Cruise Range')

        h = cls.state['h']
        hftClimb = cls.state['hft']
        dhft = cls.climbP['dhft']
        hftCruise = crs.state['hft']

        # make overall constraints
        constraints = []

        constraints.extend([
            # Weight constraints
            TCS([aircraft['W_{fuse}'] + aircraft['W_{payload}'] + W_ftotal + aircraft['numeng']
                 * aircraft['W_{engine}'] + aircraft.wing.wb['W_{struct}'] <= W_total]),

            cls.climbP.aircraftP['W_{start}'][0] == W_total,
            cls.climbP.aircraftP[
                'W_{end}'][-1] == crs.cruiseP.aircraftP['W_{start}'][0],
            TCS([cls.climbP.aircraftP['W_{start}'] >= cls.climbP.aircraftP[
                'W_{end}'] + cls.climbP.aircraftP['W_{burn}']]),
            TCS([crs.cruiseP.aircraftP['W_{start}'] >= crs.cruiseP.aircraftP[
                'W_{end}'] + crs.cruiseP.aircraftP['W_{burn}']]),

            cls.climbP.aircraftP['W_{start}'][
                1:] == cls.climbP.aircraftP['W_{end}'][:-1],
            crs.cruiseP.aircraftP['W_{start}'][
                1:] == crs.cruiseP.aircraftP['W_{end}'][:-1],

            TCS([aircraft['W_{fuse}'] + aircraft['W_{payload}'] + aircraft['numeng'] * aircraft['W_{engine}'] + \
                 aircraft.wing.wb['W_{struct}'] <= crs.cruiseP.aircraftP['W_{end}'][-1]]),

            # Fuel burned in climb and cruise
            TCS([W_ftotal >= W_fclimb + W_fcruise]),
            TCS([W_fclimb >= sum(cls.climbP['W_{burn}'])]),
            TCS([W_fcruise >= sum(crs.cruiseP['W_{burn}'])]),

            # Altitude constraints
            hftCruise == CruiseAlt,
            TCS([hftClimb[1:Ncruise] >= hftClimb[:Ncruise - 1] + dhft]),
            TCS([hftClimb[0] >= dhft[0]]),
            hftClimb[-1] <= hftCruise,

            # Compute the dh (climb rate)
            dhft == hftCruise / Nclimb,

            # Constrain the thrust
            cls.climbP.engineP['thrust'] <= 2 * \
            max(crs.cruiseP.engineP['thrust']),

            # Set the range for each cruise segment, doesn't take credit for climb
            # down range disatnce covered
            crs.cruiseP['Rng'] == ReqRng / (Ncruise),

            # Set the TSFC
            cls.climbP.engineP['TSFC'] == .7 * units('1/hr'),
            crs.cruiseP.engineP['TSFC'] == .5 * units('1/hr'),

            # Wing constraints
            aircraft.wing['W_{fuel_{wing}}'] == W_ftotal,
            cls.climbP.wingP['L_w'] == cls.climbP.aircraftP['W_{avg}'],
            crs.cruiseP.wingP['L_w'] == crs.cruiseP.aircraftP['W_{avg}'],

            aircraft.VT['T_e'] == cls.climbP.engineP['thrust'][0],

            # Vertical tail constraints
            # Drag of a windmilling engine
            aircraft.VT['D_{wm}'] >= 0.5*aircraft.VT['\\rho_{TO}']*aircraft.VT['V_1']**2*aircraft.engine['A_2']*aircraft.VT['C_{D_{wm}}'],
            
            aircraft.VT['x_{CG_{vt}}'] <= aircraft.fuse['l_{fuse}'],

            TCS([aircraft.wing['x_w'] >= crs['x_{CG}'] + crs['\\Delta x_w']]),

        ])

        #Horizontal Tail Constraints
        with SignomialsEnabled():
            constraints.extend([

                # Fuselage / horizontal tail x-location constraints
                TCS([crs['x_{CG}'] + crs['\\Delta x_{{trail}_h}'] <= aircraft.fuse['l_{fuse}']], reltol=0.002),
                TCS([aircraft.HT['x_{CG_{ht}}'] >= crs['x_{CG}']+(crs['\\Delta x_{{lead}_h}']+crs['\\Delta x_{{trail}_h}'])/2]),


                # Trim condition for each flight segment
                # aircraft.wing['c_{m_{w}}'] == 1.0,
                # crs['x_{ac}'] >= 10*units('m'),
                # cls['x_{ac}'] >= 10*units('m'),

                # crs['C_{L_h}'] >= 0.1,
                # crs['C_{L}'] >= 0.01,
                # aircraft.wing['\\bar{c}_w'] >= 0.01*units('m'),
                # crs['x_{CG}'] >= 10*units('m'),
                # crs['x_{ac}'] >= 10*units('m'),
                # aircraft.HT['V_{h}'] >= 0.01,
                # aircraft.wing['c_{m_{w}}'] >= 0.05,

                TCS([crs['x_{ac}']/aircraft.wing['\\bar{c}_w'] <= crs['c_{m_{w}}']/crs['C_{L}'] + \
                    crs['x_{CG}']/aircraft.wing['\\bar{c}_w'] + aircraft.HT['V_{h}']*(crs['C_{L_h}']/crs['C_{L}'])]), #[SP]

                # HT AoA constraint
                #REMOVE FROM OVERALL MODEL
                crs['\\alpha'] <= aircraft.HT['\\alpha_{max,h}'],
                cls['\\alpha'] <= aircraft.HT['\\alpha_{max,h}'],
                # HT cruise trim constraints
                crs['C_{L_h}'] <= 1.1*crs['C_{L_{ah}}']*crs['\\alpha'],
                crs['C_{L_h}'] >= 0.9*crs['C_{L_{ah}}']*crs['\\alpha'],

                # Aoa matching between wing and horizontal tail
                crs['\\alpha'] == crs['\\alpha_w'],
                cls['\\alpha'] == cls['\\alpha_w'],
                
                # Horizontal tail x-location constraints
                TCS([cls['x_{CG}'] + cls['\\Delta x_{{trail}_h}'] <= aircraft.fuse['l_{fuse}']], reltol=0.002),
                aircraft.HT['l_{ht}'] >= aircraft.HT['x_{CG_{ht}}'] - cls['x_{CG}'],
                TCS([aircraft.wing['x_w'] >= cls['x_{CG}'] + cls['\\Delta x_w']]),

                # Compute the aerodynamic center location
                TCS([cls['x_{ac}'] <= cls['x_{CG}'] + cls['\\Delta x_w'] ]),

##                SignomialEquality(cls['x_{ac}'],xcg + cls['\\Delta x_w'] ),
                TCS([aircraft.HT['x_{CG_{ht}}'] >= cls['x_{CG}'] + \
                    (cls['\\Delta x_{{lead}_h}'] + cls['\\Delta x_{{trail}_h}']) / 2]),
                    
                TCS([crs['x_{ac}'] <= crs['x_{CG}'] + crs['\\Delta x_w'] ]),
                # SignomialEquality(crs['x_{ac}'],crs['x_{CG}'] + crs['\\Delta x_w'] ),
                TCS([aircraft.HT['x_{CG_{ht}}'] >= crs['x_{CG}']+(crs['\\Delta x_{{lead}_h}']+crs['\\Delta x_{{trail}_h}'])/2]),
                ])
                                      

        self.cost = W_ftotal

        return constraints, aircraft, cls, crs 

if __name__ == '__main__':
    substitutions = {
        # 'V_{stall}'   : 120,
        '\\delta_P_{over}': 12,
        'N_{land}': 6,
        'SPR': 8,
        'p_s': 81.,
        # ('sweep', np.linspace(500,2000,4)),
        'ReqRng': 1000,
        # ('sweep', np.linspace(20000,40000,4)),
        'CruiseAlt': 30000,
        'numeng': 2,
        # 'W_{Load_max}': 6664,
        'n_{pax}': 150,
        'W_{avg. pass}': 180,
        'W_{carry on}': 15,
        'W_{cargo}': 10000,
        'W_{checked}': 40,
        'w_{aisle}': 0.51,
        'w_{seat}': 0.5,
        'w_{sys}': 0.1,
        # 'e': .9,
        # 'b_{max}'                 : 35,
        'W_{cargo}': 10000,
        'r_E': 1,  # [TAS]
        '\\lambda_{cone}': 0.4,  # [Philippe]
        '\\rho_{cone}': 2700,  # [TAS]
        '\\rho_{bend}': 2700,  # [TAS]
        '\\rho_{floor}': 2700,  # [TAS]
        '\\rho_{skin}': 2700,  # [TAS]
        'W\'\'_{floor}': 60,  # [TAS]
        'W\'\'_{insul}': 22,  # [TAS]
        'W\'_{seat}': 150,  # [TAS]
        'W\'_{window}': 145. * 3,  # [TAS]
        'f_{fadd}': 0.2,  # [TAS]
        'f_{frame}': 0.25,  # [Philippe]
        'f_{lugg,1}': 0.4,  # [Philippe]
        'f_{lugg,2}': 0.1,  # [Philippe]
        'f_{string}': 0.1,  #TODO remove
        'f_{padd}': 0.4,  # [TAS]

        # wing subs
        'C_{L_{wmax}}': 2.5,
        # 'V_{ne}': 144,
        '\\tan(\\Lambda)': tan(sweep * pi / 180),
        '\\alpha_{max,w}': 0.1,  # (6 deg)
        '\\cos(\\Lambda)': cos(sweep * pi / 180),
        '\\eta': 0.97,
        '\\rho_{fuel}': 817,  # Kerosene [TASOPT]

        #VT subs
       'C_{D_{wm}}': 0.5, # [2]
       'C_{L_{vmax}}': 2.6, # [2]
       'V_1': 70,
       '\\rho_{TO}': 1.225,
        '\\tan(\\Lambda_{vt})': np.tan(40*np.pi/180),
##           'c_{l_{vt}}': 0.5, # [2]
        'c_{l_{vtEO}}': 0.5,
        'A_2': np.pi*(.5*1.75)**2, # [1]
        'e_v': 0.8,
##           'x_{CG}': 18,
        'y_{eng}': 4.83, # [3]

        'V_{land}': 72,
        'I_{z}': 12495000, #estimate for late model 737 at max takeoff weight (m l^2/12)
        '\\dot{r}_{req}': 0.174533, #10 deg/s yaw rate

        'N_{spar}': 2,

        # HT subs
        '\\tan(\\Lambda_{ht})': tan(30*pi/180),
        # 'c_{m_{w}}': 1,
        '\\alpha_{max,h}': 2.5,
        'SM_{min}': 0.15,
        '\\Delta x_{CG}': 4,
        '\\bar{c}_w': 2,
    }

    m = Mission()
    m.substitutions.update(substitutions)
    # m = Model(m.cost,BCS(m))
    sol = m.localsolve(solver='mosek', verbosity = 2, iteration_limit = 100)
    # bounds, sol = m.determine_unbounded_variables(
    #     m, solver="mosek", verbosity=2, iteration_limit=50)
