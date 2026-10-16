# MULO — Optimisation de la durée de vie des roulements

# Étude ACV simplifiée : minimisation des émissions de CO₂ par km

# Objectif : déterminer, pour une stratégie de remplacement donnée, le nombre de  kilomètres d'utilisation d'un roulement qui minimise les émissions moyennes de CO₂ par kilomètre.


# ============================================================
# 1. IMPORTS & CONFIG
# ============================================================

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import json
from pathlib import Path
from dataclasses import dataclass
from scipy.interpolate import interp1d, RegularGridInterpolator

# Affichage des graphiques
plt.rcParams["figure.figsize"] = (9, 5)
plt.rcParams["axes.grid"] = True
plt.rcParams["figure.dpi"] = 110

# ============================================================
# 2. PARAMETRES D'ETUDE - OPTIONS UTILISATEUR
# ============================================================

SELECTED_BEARINGS = [
    "SKF 6307-2RS1",
    "SKF NU 2206 ECP"
]

ALPHA_VALUES = [0.5, 2, 5, 10, 20]
BETA_VALUES = [0.5, 1, 2, 3, 4]

N_INTEGRATION_POINTS = 500

USAGE_PROFILE = {
    "roulage": 0.70,                #70% du temps à vitesse constante
    "acceleration_max": 0.15,       #15% d'accélération + chocs
    "freinage_max": 0.15
}

SHOW_CONSOLE_RESULTS = True
SHOW_GRAPHICAL_RESULTS = True

SHOW_FRICTION = True
SHOW_AVERAGE_CO2 = True
SHOW_ALPHA_SENSITIVITY = True
SHOW_BETA_SENSITIVITY = True
SHOW_CO2_EVOLUTION = True
SHOW_OPTIMIZATION = True

# ============================================================
# 3. IMPORTATION DES PARAMÈTRES GÉNÉRAUX DU PROJET
# ============================================================

@dataclass
class VehicleConfig:
    wheel_radius_m: float
    vehicle_avg_speed_kmh: float
    vehicle_max_speed_kmh: float
    electricity_co2_g_per_kwh: float
    grid_to_wheel_efficiency: float
    vehicle_lifetime_km: float
    
    @property
    def distance_per_rev_m(self):
        return 2 * np.pi * self.wheel_radius_m
    
    @property
    def wheel_rpm_avg(self):
        return (60*self.vehicle_avg_speed_kmh/3.6) / self.distance_per_rev_m
    
    @property
    def wheel_rpm_max(self):
        return (60*self.vehicle_max_speed_kmh/3.6) / self.distance_per_rev_m
    
    @property
    def omega_avg(self):
        return 2 * np.pi * self.wheel_rpm_avg / 60
    
    @property
    def omega_max(self):
        return 2 * np.pi * self.wheel_rpm_max / 60


def load_config(filename="vehicle.json"):
    with open(filename, "r") as f:
        data = json.load(f)
    return VehicleConfig(**data)

vehicle = load_config()

# ============================================================
# Affichage config véhicule
# ============================================================


print("Chargement des données du véhicule:")
print(f"Rayon des roues : {vehicle.wheel_radius_m} [m]")
print(f"Vitesse max : {vehicle.vehicle_max_speed_kmh} [km/h]")
print(f"Vitesse moyenne : {vehicle.vehicle_avg_speed_kmh} [km/h]")
print(f"Profile de déplacement utilisé : {USAGE_PROFILE}")

# ============================================================
# 4. CLASSE DE DONNÉES POUR LE MODELE DE FRICTION
# ============================================================
    
@dataclass
class FrictionModel:
    friction_file: str
    torque_interp: object = None
    
    def load_data(self):
        data = pd.read_excel(
            self.friction_file,
            header=0)
        return data
    
    def build_interpolator(self):
        friction_data = self.load_data()
        friction_data.columns = (friction_data.columns.str.strip())
        fr_values = np.sort(friction_data["Force Radiale [N]"].unique())
        fa_values = np.sort(friction_data["Force Axiale [N]"].unique())
        rpm_columns = [c for c in friction_data.columns if "RPM" in c]
        rpm_values = np.array([int(c.split()[0]) for c in rpm_columns])
        torque_grid = np.zeros((len(fr_values), len(fa_values), len(rpm_values)))
        for i, fr in enumerate(fr_values):
            for j, fa in enumerate(fa_values):
                row = friction_data[(friction_data["Force Radiale [N]"] == fr) & (friction_data["Force Axiale [N]"] == fa)]
                torque_grid[i, j, :] = (row[rpm_columns].values[0])

        self.torque_interp = (RegularGridInterpolator((fr_values, fa_values, rpm_values), torque_grid, bounds_error=True, fill_value=None))
        
    def get_torque(self, fr, fa, rpm):
        if self.torque_interp is None:            
            raise RuntimeError("Interpolator not initialized")
        torque_nmm = float(self.torque_interp([[fr, fa, rpm]])[0])            
        return torque_nmm / 1000
    
# ============================================================
# 5. CLASSE DE DONNÉES POUR LE CHARGEMENT DES ROULEMENTS
# ============================================================ 

@dataclass
class LoadModel:

    loads_file: str
    loads: dict = None
    
    def load(self):
        try:
            with open(
                self.loads_file,
                "r",
                encoding="utf-8"
            ) as f:
                self.loads = json.load(f)
        except json.JSONDecodeError as e:
            print(f"Erreur JSON dans {self.loads_file}")
            print(e)
            raise
    
    def get_case(self, name):
        data = self.loads[name]
    
        Fx = data["Fx_N"]
        Fy = data["Fy_N"]
        Fz = data["Fz_N"]
    
        return {"Fx_N": Fx, "Fy_N": Fy, "Fz_N": Fz, "Fr_N": np.hypot(Fx, Fz), "Fa_N": abs(Fy)}
    
# ============================================================
# 6. CLASSE DE DONNÉES POUR LES FACTEURS DE CHARGE RLMT
# ============================================================ 

@dataclass
class SKFLoadFactors:
    
    coeff_file: str
    ratio_values: np.ndarray = None
    e_values: np.ndarray = None
    X_values: np.ndarray = None
    Y_values: np.ndarray = None
    
    def load(self):
        data = pd.read_excel(self.coeff_file)
        self.ratio_values = (data["f0*Fa/C0"].values)
        self.e_values = (data["e"].values)
        self.X_values = (data["X"].values)
        self.Y_values = (data["Y"].values)
        self.e_interp = interp1d(self.ratio_values, self.e_values, fill_value="extrapolate")  
        self.X_interp = interp1d(self.ratio_values, self.X_values, fill_value="extrapolate")
        self.Y_interp = interp1d(self.ratio_values, self.Y_values, fill_value="extrapolate")
        
    def get_factors(self, ratio):
        return (float(self.e_interp(ratio)), float(self.X_interp(ratio)), float(self.Y_interp(ratio)))
        
# ============================================================
# 7. CLASSE DE DONNÉES POUR ROULEMENT 
# ============================================================     
  
@dataclass
class Bearing:
    # --------------------------------------------------------
    # Données générales et environnementales d'un roulement
    # --------------------------------------------------------

    name: str
    position: str
    quantity: int
    mass_kg: float = np.nan
    bearing_type: str = "ball"
    
    # --------------------------------------------------------
    # Caractéristiques
    # --------------------------------------------------------
    
    f0: float = np.nan
    supports_axial_load: bool = False
    skf_factors: SKFLoadFactors = None
    dynamic_capacity_N: float = np.nan
    static_capacity_N : float = np.nan
    speed_limit_rpm: float = np.nan

    # --------------------------------------------------------
    # ACV - Impact CO2 fixe
    # --------------------------------------------------------
    # Valeurs par roulement [g CO2-eq / pièce]

    manufacturing_co2_g: float = np.nan
    distribution_co2_g: float = np.nan
    end_of_life_co2_g: float = np.nan

    # --------------------------------------------------------
    # ACV - Maintenance
    # --------------------------------------------------------

    maintenance_co2_g: float = np.nan
    maintenance_interval_rev: float = np.inf
    
    # --------------------------------------------------------
    # Chargement du modèle de friction
    # --------------------------------------------------------
    
    friction_file: str = ""
    friction_model: FrictionModel = None
    mean_torque_cache: float = None
    
    # --------------------------------------------------------
    # Chargement des charges appliquées sur le roulement
    # --------------------------------------------------------
    
    loads_file: str = ""
    load_model: LoadModel = None
    L10_mean_cache : float = None
    
    @property
    def fixed_co2_g(self):
        return (self.manufacturing_co2_g + self.distribution_co2_g + self.end_of_life_co2_g)
    
    @property
    def life_exponent(self):
        if self.bearing_type == "roller":
            return 10/3
        return 3
    
    # --------------------------------------------------------
    # Obtention des données de couple résistif
    # --------------------------------------------------------
    
    def get_torque(self, fr, fa, rpm):
        return (self.friction_model.get_torque(fr, fa, rpm))
    
    def get_torque_for_case(self, case_name, rpm):
        case = self.load_model.get_case(case_name)
        return self.get_torque(case["Fr_N"], case["Fa_N"], rpm)
    
    def get_mean_torque(self, usage_profile, rpm):
        if self.mean_torque_cache is not None:
            return self.mean_torque_cache
        M_mean = 0
        for case_name, weight in usage_profile.items():
            M_case = self.get_torque_for_case(case_name, rpm)
            M_mean += weight * M_case
        self.mean_torque_cache = M_mean
        return M_mean
    
    # --------------------------------------------------------
    # Calcul de durée de vie L10
    # --------------------------------------------------------
    
    def equivalent_dynamic_load(self, case_name):
        case = self.load_model.get_case(case_name)
        Fr = case["Fr_N"]
        Fa = case["Fa_N"]
        if not self.supports_axial_load:
            return Fr
        if Fa == 0:
            return Fr
        ratio = (self.f0 * Fa / self.static_capacity_N)
        e, X, Y = (self.skf_factors.get_factors(ratio))
        if Fa / Fr <= e:
            return Fr
        return (X*Fr + Y*Fa)
    
    def equivalent_dynamic_load_mean(self, usage_profile):
        P_mean = 0
        for case_name, weight in usage_profile.items():
            P_case = self.equivalent_dynamic_load(case_name)
            P_mean += weight * P_case
        return P_mean
    
    def calculate_L10(self, case_name="roulage"):
        P = self.equivalent_dynamic_load(case_name)
        p = self.life_exponent
        return ((self.dynamic_capacity_N / P)** p * 1e6)
    
    def calculate_L10_mean(self, usage_profile):
        if self.L10_mean_cache is not None:
            return self.L10_mean_cache
        P = self.equivalent_dynamic_load_mean(usage_profile)
        self.L10_mean_cache = ((self.dynamic_capacity_N / P) ** self.life_exponent * 1e6)
        return self.L10_mean_cache
    
    def calculate_L10_km(self, case_name="roulage"):
        L10_rev = self.calculate_L10(case_name)
        return revolutions_to_km(L10_rev)
    
    def calculate_L10_mean_km(self, usage_profile):
        return revolutions_to_km(self.calculate_L10_mean(usage_profile))
    
    # --------------------------------------------------------
    # Vieillissement des roulements
    # --------------------------------------------------------
    
    def wear_factor(self, revolutions, usage_profile, alpha=0.5, beta=2):
        L10 = self.calculate_L10_mean(usage_profile)
        return (1 + alpha * (revolutions / L10) ** beta)
    
    def get_worn_mean_torque(self, usage_profile, rpm, revolutions, alpha=0.5, beta=2):
        M_mean = self.get_mean_torque(usage_profile, rpm)
        return (M_mean * self.wear_factor(revolutions, usage_profile, alpha, beta))
            
    
    # --------------------------------------------------------
    # Chargement des modèles post-initialisation
    # --------------------------------------------------------
    
    def __post_init__(self):
        if self.friction_file:
            self.friction_model = FrictionModel(self.friction_file)
            self.friction_model.build_interpolator()
        
        if self.loads_file:
            self.load_model = LoadModel(self.loads_file)
            self.load_model.load()
            
        if self.supports_axial_load:
            self.skf_factors = SKFLoadFactors("./bearings/Bearing_Coef.xlsx")
            self.skf_factors.load()
            
# ============================================================
# 8. LISTE DES ROULEMENTS A PARTIR DES FICHIERS JSON
# ============================================================

def load_bearing(json_file):
    with open(json_file, "r") as f:
        data = json.load(f)
    return Bearing(**data)

bearing_folder = Path("bearings")
bearings = []

for file in bearing_folder.glob("*.json"):
    bearings.append(
        load_bearing(file)
    )

print(f"\nRoulements sélectionnés : {SELECTED_BEARINGS}")
for b in bearings:
    print(f"\nChargement des données du roulement {b.name}")
    print(f"Fichier de données : {b.friction_file}")


# ============================================================
# 9. CONVERTION ROTATION EN DISTANCE ET INVERSEMENT
# ============================================================

def revolutions_to_km(revolutions):
    """Convertit des rotations de roue en kilomètres."""
    return np.asarray(revolutions) * vehicle.distance_per_rev_m / 1000


def km_to_revolutions(distance_km):
    """Convertit des kilomètres en rotations de roue."""
    return np.asarray(distance_km) * 1000 / vehicle.distance_per_rev_m


# ============================================================
# 10. DISSIPATION D'ENERGIE ET CONVERSION ENERGIE ==> CO2
# ============================================================

def energy_per_revolution(torque):
    return torque * 2 * np.pi

def energy_per_km(torque):
    return energy_per_revolution(torque) * (1000 / vehicle.distance_per_rev_m)

def energy_to_co2(energy_J):
    energy_kWh = energy_J / 3.6e6
    return energy_kWh * (vehicle.electricity_co2_g_per_kwh / vehicle.grid_to_wheel_efficiency)

# ------------------------------------------------------------
# 11. CALCULS ACV + SENSIBILITE
# ------------------------------------------------------------

def friction_co2_over_life(bearing, replacement_km, alpha=0.5, beta=2):
    km_values = np.linspace(0, replacement_km, N_INTEGRATION_POINTS)
    co2_per_km_values = []

    for km in km_values:
        rev = km_to_revolutions(km)
        M = bearing.get_worn_mean_torque(USAGE_PROFILE, vehicle.wheel_rpm_avg, rev, alpha=alpha, beta=beta)
        E_km = energy_per_km(M)
        co2_per_km_values.append(energy_to_co2(E_km))

    return np.trapz(co2_per_km_values, km_values)

def friction_co2_over_vehicle_life(bearing, replacement_km, alpha=0.5, beta=2):
    remaining_km = vehicle.vehicle_lifetime_km
    co2_total = 0
    while remaining_km > 0:
        segment_km = min(replacement_km, remaining_km)
        co2_total += friction_co2_over_life(bearing, segment_km, alpha=alpha, beta=beta)
        remaining_km -= segment_km
        
    return co2_total


def total_co2_per_km(bearing, replacement_km, alpha=0.5, beta=2):
    n_bearings = np.ceil(vehicle.vehicle_lifetime_km / replacement_km)
    co2_fixed_total = (n_bearings * bearing.fixed_co2_g)
    co2_friction_total = (friction_co2_over_vehicle_life(bearing, replacement_km, alpha=alpha, beta=beta))
    co2_total = (co2_fixed_total  + co2_friction_total)
    
    return (co2_total / vehicle.vehicle_lifetime_km)

def average_co2_vehicle_life(bearing, replacement_km, alpha=0.5):
    km_values = np.linspace(10000, vehicle.vehicle_lifetime_km, N_INTEGRATION_POINTS)
    delta_km = (km_values[1]  - km_values[0])
    co2_total = bearing.fixed_co2_g
    co2_average = []
    next_replacement = replacement_km
    for km in km_values:
        while km >= next_replacement:
            co2_total += (bearing.fixed_co2_g)
            next_replacement += (replacement_km)
        km_bearing = (km % replacement_km)
        rev = km_to_revolutions(km_bearing)
        M = bearing.get_worn_mean_torque(USAGE_PROFILE, vehicle.wheel_rpm_avg, rev, alpha=alpha)
        co2_per_km = energy_to_co2(energy_per_km(M))
        co2_total += (co2_per_km * delta_km)
        co2_average.append(co2_total / km)

    return (km_values, co2_average)

def compute_optimization(bearing, alpha=0.5, beta=2):
    replacement_values = np.linspace(10_000, vehicle.vehicle_lifetime_km, N_INTEGRATION_POINTS)
    co2_values = []
    for replacement_km in replacement_values:
        co2_values.append(total_co2_per_km(bearing, replacement_km, alpha=alpha, beta=beta))
    idx_min = np.argmin(co2_values)

    return {"replacement_values": replacement_values, "co2_values": co2_values, "optimal_km": replacement_values[idx_min], "optimal_co2": co2_values[idx_min]}

def compute_alpha_sensitivity(bearing):
    results = {}
    for alpha in ALPHA_VALUES:
        results[alpha] = (compute_optimization(bearing, alpha=alpha))
    return results

def compute_beta_sensitivity(bearing, alpha=10):
    results = {}
    for beta in BETA_VALUES:
        results[beta] = (compute_optimization(bearing, alpha=alpha, beta=beta))
    return results

analysis_results = {}

# ------------------------------------------------------------
# 12. AFFICHAGE CONSOLE - Résumé Principal
# ------------------------------------------------------------

def print_bearing_summary(bearing):
    print()
    print("=" * 60)
    print(bearing.name)
    print("=" * 60)

    # --------------------------------------------------
    # Caractéristiques
    # --------------------------------------------------
    
    print("\n[CARACTERISTIQUES]")
    print(f"Masse               : {bearing.mass_kg:.3f} [kg]")
    print(f"Capacité dynamique  : {bearing.dynamic_capacity_N:,.0f} [N]")
    print(f"Capacité statique   : {bearing.static_capacity_N:,.0f} [N]")
    print(f"CO2 fabrication     : {bearing.manufacturing_co2_g:.0f} [g]")

    # --------------------------------------------------
    # Frottement
    # --------------------------------------------------
    
    print("\n[FROTTEMENT]")
    M = bearing.get_mean_torque(USAGE_PROFILE, vehicle.wheel_rpm_avg)
    E_km = energy_per_km(M)
    co2_km = energy_to_co2(E_km)
    print(f"Couple moyen        : {M:.3f} [N.m]")
    print(f"Energie/km          : {E_km:.0f} [J]")
    print(f"CO2/km              : {co2_km:.3f} [g]")

    # --------------------------------------------------
    # Durée de vie nominale
    # --------------------------------------------------
    
    print("\n[DUREE DE VIE]")
    P_mean = (bearing.equivalent_dynamic_load_mean(USAGE_PROFILE))
    L10_km = (bearing.calculate_L10_mean_km(USAGE_PROFILE))
    print(f"P moyen             : {P_mean:.0f} [N]")
    print(f"L10                 : {L10_km:,.0f} [km]")
    print(f"Utilisation MULO    : {vehicle.vehicle_lifetime_km/L10_km:.2%}")

    # --------------------------------------------------
    # Usure - Augmentation du couple
    # --------------------------------------------------
    
    print("\n[USURE - AUGMENTATION DU COUPLE]")
    for km in [0, 250000, 500000, 750000, 1000000]:
        rev = km_to_revolutions(km)
        M = (bearing.get_worn_mean_torque(USAGE_PROFILE, vehicle.wheel_rpm_avg, rev))
        print(f"{km:>8,.0f} km -> {M:.4f} [N.m]")

    # --------------------------------------------------
    # ACV - Scénarios de remplacement
    # --------------------------------------------------
    
    print("\n[ACV - SCENARIOS DE REMPLACEMENT]")
    for replacement_km in [(vehicle.vehicle_lifetime_km/10), (vehicle.vehicle_lifetime_km/5), (vehicle.vehicle_lifetime_km/3), (vehicle.vehicle_lifetime_km/2), (vehicle.vehicle_lifetime_km)]:
        co2 = total_co2_per_km(bearing, replacement_km)
        print(f"{replacement_km:>8,.0f} km -> {co2:.4f} [g/km]")
        
# --------------------------------------------------
# 13. AFFICHAGE CONSOLE - Optimisation des changements
# --------------------------------------------------

def print_bearing_optimization(bearing, analysis_result):    
    print("\n[OPTIMISATION DU REMPLACEMENT - CAS STANDARD]")
    optimization = (analysis_result["optimization"])
    print(f"Distance optimale : {optimization['optimal_km']:,.0f} [km]")
    print(f"CO2 minimal : {optimization['optimal_co2']:.4f} [g/km]")
    
    # --------------------------------------------------
    # ACV - Sensibilité sur alpha
    # --------------------------------------------------
    
    print("\n[SENSIBILITE ALPHA - BETA = 2]")
    alpha_results = (analysis_result["alpha_sensitivity"])
    for alpha, result in alpha_results.items():
        print(f"alpha ={alpha:>4} -> optimum = {result['optimal_km']:,.0f} km | CO2 = {result['optimal_co2']:.4f} [g/km]")
        
    # --------------------------------------------------
    # ACV - Sensibilité sur beta
    # --------------------------------------------------
    
    print("\n[SENSIBILITE BETA - ALPHA = 10]")
    beta_results = (analysis_result["beta_sensitivity"])
    for beta, result in beta_results.items():
        print(f"beta ={beta:>4} -> optimum = {result['optimal_km']:,.0f} km | CO2 = {result['optimal_co2']:.4f} [g/km]")

selected_bearings = [bearing for bearing in bearings if bearing.name in SELECTED_BEARINGS]


print("\nDébut des calculs. Veuillez patienter...")   

if SHOW_CONSOLE_RESULTS:
    for bearing in selected_bearings:
        print_bearing_summary(bearing)
        if SHOW_OPTIMIZATION:
            analysis_results[bearing.name] = {"optimization": compute_optimization(bearing), "alpha_sensitivity": compute_alpha_sensitivity(bearing), "beta_sensitivity": compute_beta_sensitivity(bearing)}
            print_bearing_optimization(bearing, analysis_results[bearing.name])

# ------------------------------------------------------------
# 14. AFFICHAGE DES RESULTATS GRAPHIQUES
# ------------------------------------------------------------
# ------------------------------------------------------------
# Evolution du frottement
# ------------------------------------------------------------

def plot_friction_evolution(bearing):
    km_values = np.linspace(0, vehicle.vehicle_lifetime_km, N_INTEGRATION_POINTS)
    torques = []
    for km in km_values:
        rev = km_to_revolutions(km)
        M = bearing.get_worn_mean_torque(USAGE_PROFILE, vehicle.wheel_rpm_avg, rev)
        torques.append(M)
        
    plt.figure()
    plt.plot(km_values,torques,label="Couple de frottement - α=0.5")
    plt.xlabel("Distance parcourue [km]")
    plt.ylabel("Couple de frottement moyen [N.m]")
    plt.title(f"Evolution du frottement - {bearing.name}")
    plt.legend()
    plt.show()
    
# ------------------------------------------------------------
# Etude de sensibilité sur alpha
# ------------------------------------------------------------

def plot_torque_alpha_sensitivity(bearing):
    km_values = np.linspace(0, vehicle.vehicle_lifetime_km, N_INTEGRATION_POINTS)
    torques = []
    plt.figure()
    for alpha in ALPHA_VALUES:
        torques = []
        for km in km_values:
            rev = km_to_revolutions(km)
            M = bearing.get_worn_mean_torque(USAGE_PROFILE, vehicle.wheel_rpm_avg, rev, alpha=alpha)
            torques.append(M)
        plt.plot(km_values, torques, label=f"α={alpha}")
    plt.xlabel("Distance parcourue [km]")
    plt.ylabel("Couple de frottement moyen [N.m]")
    plt.title(f"Influence du coefficient d'usure - {bearing.name}")
    plt.legend()
    plt.show()
    
# ------------------------------------------------------------
# Etude de sensibilité sur beta
# ------------------------------------------------------------

def plot_torque_beta_sensitivity(bearing):
    km_values = np.linspace(0, vehicle.vehicle_lifetime_km, N_INTEGRATION_POINTS)
    torques = []
    plt.figure()
    for beta in BETA_VALUES:
        torques = []
        for km in km_values:
            rev = km_to_revolutions(km)
            M = bearing.get_worn_mean_torque(USAGE_PROFILE, vehicle.wheel_rpm_avg, rev, beta=beta)
            torques.append(M)
        plt.plot(km_values, torques, label=f"β={beta}")
    plt.xlabel("Distance parcourue [km]")
    plt.ylabel("Couple de frottement moyen [N.m]")
    plt.title(f"Influence de la vitesse d'usure - {bearing.name}")
    plt.legend()
    plt.show()
    
# ------------------------------------------------------------
# Évolution du CO2 de frottement
# ------------------------------------------------------------

def plot_CO2_evolution(bearing):
    km_values = np.linspace(0, vehicle.vehicle_lifetime_km, N_INTEGRATION_POINTS)
    plt.figure()
    for alpha in ALPHA_VALUES:
        co2_values = []
        for km in km_values:
            rev = km_to_revolutions(km)
            M = bearing.get_worn_mean_torque(USAGE_PROFILE, vehicle.wheel_rpm_avg, rev, alpha=alpha)
            E_km = energy_per_km(M)
            co2_km = energy_to_co2(E_km)
            co2_values.append(co2_km)
        plt.plot(km_values, co2_values, label=f"α={alpha}")
    plt.xlabel("Distance parcourue [km]")
    plt.ylabel("CO₂ dû au frottement [g/km]")
    plt.title(f"Evolution du CO₂ de frottement - {bearing.name}")
    plt.legend()
    plt.show()

# ------------------------------------------------------------
# Distance optimale de remplacement
# ------------------------------------------------------------

def plot_bearing_replacement(bearing, optimization_result):
    replacement_values = optimization_result["replacement_values"]
    co2_values = optimization_result["co2_values"]   
    optimal_km = optimization_result["optimal_km"]
    plt.figure()
    plt.plot(replacement_values, co2_values)
    plt.axvline(optimal_km, color="red", linestyle="--")
    plt.xlabel("Distance de remplacement [km]")
    plt.ylabel("CO₂ total [g/km]")
    plt.title(f"Optimisation du remplacement - {bearing.name}")
    plt.grid(True)
    plt.show()
    

# ------------------------------------------------------------
# Sensibilité de la distance de remplacement optimale à alpha
# ------------------------------------------------------------

def plot_replacement_alpha_sensitivity(bearing, alpha_results):
    plt.figure()
    for alpha in ALPHA_VALUES:
        result = alpha_results[alpha]
        plt.plot(result["replacement_values"], result["co2_values"], label=f"α={alpha}")
        #plt.scatter(result["optimal_km"], result["optimal_co2"], marker="o")
    plt.xlabel("Distance de remplacement [km]")
    plt.ylabel("CO₂ total [g/km]")
    plt.title(f"Sensibilité à l'usure - {bearing.name}")
    plt.grid(True)
    plt.legend()
    plt.show()

# ------------------------------------------------------------
# Sensibilité de la distance de remplacement optimale à beta
# ------------------------------------------------------------

def plot_replacement_beta_sensitivity(bearing, beta_results):
    plt.figure()
    for beta in BETA_VALUES:
        result = beta_results[beta]
        plt.plot(result["replacement_values"], result["co2_values"], label=f"β={beta}")
        #plt.scatter(result["optimal_km"], result["optimal_co2"], marker="o")
    plt.xlabel("Distance de remplacement [km]")
    plt.ylabel("CO₂ total [g/km]")
    plt.title(f"Sensibilité à l'usure - {bearing.name}")
    plt.grid(True)
    plt.legend()
    plt.show()

# ------------------------------------------------------------
# Total CO2 emis moyen sur la vie du véhicule
# ------------------------------------------------------------

def plot_average_co2_vehicle_life(bearing):
    replacement_scenarios = [100000, 300000, 500000, 1000000]
    plt.figure()
    for replacement_km in replacement_scenarios:
        km_values, co2_values = (average_co2_vehicle_life(bearing, replacement_km=replacement_km))
        plt.plot(km_values, co2_values, label=f"Remplacement tous les {replacement_km:,.0f} [km]")
    plt.xlabel("Distance parcourue [km]")
    plt.ylabel("Empreinte carbone moyenne cumulée [gCO₂e/km]")
    plt.title(f"CO₂ moyen au cours de la vie du véhicule - {bearing.name}")
    plt.legend()
    plt.grid(True)
    plt.show()

if SHOW_GRAPHICAL_RESULTS:
    for bearing in selected_bearings:
        if SHOW_FRICTION:
            plot_friction_evolution(bearing)
        if SHOW_ALPHA_SENSITIVITY:
            plot_torque_alpha_sensitivity(bearing)
        if SHOW_BETA_SENSITIVITY:    
            plot_torque_beta_sensitivity
        if SHOW_AVERAGE_CO2:
            plot_average_co2_vehicle_life(bearing)
        if SHOW_CO2_EVOLUTION and SHOW_ALPHA_SENSITIVITY:
            plot_CO2_evolution(bearing)
        if SHOW_OPTIMIZATION:
            plot_bearing_replacement(bearing, analysis_results[bearing.name]["optimization"])
            if SHOW_ALPHA_SENSITIVITY:
                plot_replacement_alpha_sensitivity(bearing, analysis_results[bearing.name]["alpha_sensitivity"])
            if SHOW_BETA_SENSITIVITY:
                plot_replacement_beta_sensitivity(bearing, analysis_results[bearing.name]["beta_sensitivity"])
