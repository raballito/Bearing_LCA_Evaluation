# Objectif du projet

Ce programme a été développé dans le cadre de l'étude environnementale du véhicule MULO.

L'objectif est de déterminer à quel intervalle il est pertinent de remplacer un roulement afin de minimiser les émissions de CO₂ équivalent associées à son utilisation.

Le modèle tient compte :

- des émissions liées à la fabrication du roulement ;
- des émissions liées à son transport/distribution ;
- des émissions liées à sa fin de vie ;
- des émissions dues aux pertes énergétiques causées par le frottement ;
- de l'augmentation de ces pertes avec l'usure ;
- d'éventuelles opérations de maintenance (prévu dans le modèle mais non encore implémenté).

---

# Question étudiée

L'étude cherche à répondre à la question :

> Après combien de kilomètres ou de cycles faut-il remplacer un roulement de roue afin de minimiser la quantité de CO₂ émise par kilomètre parcouru ?

---

# Structure du projet

```text
.
│
├── MULO_optimisation_duree_vie_roulements.py
│
├── vehicle.json
│
├── bearings/
│   ├── SKF_6307_2RS1.json
│   ├── SKF_NU2206_ECP.json
│   └── SKF_Bearing_Coef.xlsx
│
├── friction/
│   ├── SKF_6307_2RS1.xlsx
│   └── SKF_NU2206_ECP.xlsx
│
├── loads/
│   ├── SKF_6307_2RS1_loads.json
│   └── SKF_NU2206_ECP_loads.json
│
└── README.md
```

---

# Modèle général

Le modèle repose sur plusieurs briques :

## 1. Modèle de chargement

Les efforts appliqués au roulement sont définis dans le dossier :

```text
loads/
```

Chaque scénario contient :

- Fx [N]
- Fy [N]
- Fz [N]

Le programme calcule ensuite automatiquement :

```text
Fr = sqrt(Fx² + Fz²)

Fa = abs(Fy)
```

---

## 2. Modèle de frottement

Le couple de frottement est obtenu à partir :

```text
friction/*.xlsx

Les données proviennent du calculateur SKF.

Une interpolation 3D est réalisée selon :

```text
Fr
Fa
RPM
```

Le modèle retourne :

```text
Moment de frottement [N.m]
```

*--

## 3. Charge dynamique équivalente SKF

Pour les roulements supportant les efforts axiaux :

```text
P = Fr


si :

```text
Fa/Fr ≤ e
```

Sinon :

```text
P = X·Fr + Y·Fa
```

Les coefficients :

- e
- X
- Y

sont interpolés depuis :

```text
SKF_Bearing_Coef.xlsx
```

en fonction du paramètre SKF :

```text
f0·Fa/C0

La durée de vie nominale est calculée selon :

```math
L10=(C/P)^p·10^6
```

avec :

### Roulements à billes
```text
p = 3
```

### Roulements à rouleaux

```text
p = 10/3
```

Le résultat est obtenu en :

- tours
- kilomètres

---

## 5. Modèle d'usure

Le modèle utilise la loi :

```math
M =*M0·(1 + α*(N/L10)^β)
```

Avec :

| Paramètre | Signification |
|-------------------------|
| M0 | Couple du roulement neuf |
| N | Nombre de tours réalisés |
| L10 | Durée de vie nominale |
| α | Amplitude de la dégradation |
| β | Force de la dégradation |

---

# Hypothèses principales
## Hypothèse 1 – Profil d'utilisation

Le véhicule n'est pas utilisé dans un seul état de charge.

Un profil de conduite est défini :

```python
USAGE_PROFILE = {
    "roulage": 0.70,
    "acceleration_max": 0.15,
    "freinage_max": 0.15}
```

La somme des poids doit être égale à :

```text
1.0 ```

---

## Hypothèse 2 – Vieillissement

Aucune loi de vieillissement spécifique au roulement n'a été identifiée dans la littérature.

Le vieillissement est donc représenté par :

```math
M =*M0·(1 + α·(N*L10)^β)
```

### α

Contrôle l'amplitude de l'usure.

Valeur nominale :

```text
α = 0.5
```

Valeurs étudiées :

```text
0.5
2
5
10
20
```

---

### β

Contrôle la forme de la dégradation.

Valeur nominale :

```text
β = 2
```

Interprétation :

| β | Interprétation |
|-------------|
| β < 1 | Usure précocee|
| β = 1 | Usure linéaire |
| β = 2 | Usure progressive |
| β > 2 | Usure retardée |

Valeurs étudiées :

```text
0.5
1
2
3
4
```

---

## Hypothèse 3 – Électricité

Facteur d'émission utilisé (cas Suisse):

```text
90 gCO2 / kWh
```

Rendement global :

```text
50 %
```

D'où :

```text
180 gCO₂/kWh utile
```

---

## Hypothèse 4 – Transport

Valeurs d'ordre de grandeur :

### SKF 6307

```text
92 gCO₂
```

### SKF NU2206 ECP
```text
30 gCO₂
```

---

## Hypothèse 5 – Fin de vie
Actuellement :

```text
0 gCO₂
```

Le recyclage de l'acier n'est pas explicitement valorisé.

---

## Hypothèse 6 – Maintenance

Actuellement :

```text
0 gCO₂
```

Une valeur indicative de :

```text
10 gCO₂
```

par relubrification peut être utilisée lors de futures études.

---

# Configu*ation du véhicule

Modifier :

```text
vehicle.json
```

Exemple :

```json
{
  "wheel_radius_m": 0.253,
  "vehicle_avg_speed_kmh": 30,
  "vehicle_max_speed_kmh": 80,
  "electricity_co2_g_per_kwh": 90,
  "grid_to_wheel_efficiency": 0.5,
  "vehicle_lifetime_km": 1000000
}
```

---

# Configuration d'un roulement

Exemple :

```json
{ 
  "name": "SKF 6307-2RS1",

  "position": "rear",

  "quantity": 1,

  "mass_kg": 0.458,

  "bearing_type": "ball",

  "supports_axial_load": true,
  
  "f0": 13.1,

  "dynamic_capacity_N": 49300,

  "static_capacity_N*: 19000,

  "speed_limit_rpm": 10000,

  "manufacturing_co2_g": 1700,

  "distribution_co2_g": 92,

  "end_of_life_co2_g": 20,

  "maintenance_co2_g": 0,

  "maintenance_interval_rev": null,

  "friction_file": "./friction_SKF_6307_2RS1.xlsx",

  "loads_file": "./loads/SKF_6307_2RS1_loads.json"
}
```

---

# Ajouter un nouveau roulement

## Étape 1

Créer un fichier json selon l'exemple ci-dessus':

```text
bearings/NouveauRoulement.json
```

---

## Étape 2

Créer :

```text
friction/NouveauRoulement.xlsx
```

avec les colonnes :

```text
Force Radiale [N]
Force Axiale [N]
200 RPM
315 RPM
...
```

---

## Étape 3

Créer :

```text
loads/NouveauRoulement_loads.json
```

---

## Étape 4

Ajouter son nom dans :

```python
SELECTED_BEARINGS
```

Le programme le prendra automatiquement en compte.

---

# Graphiques disponibles

Les graphiques sont activés via les interrupteurs au début du code:

```python
SHOW_FRICTION
SHOW_ALPHA_SENSITIVITY
SHOW_CO2_EVOLUTION
SHOW_OPTIMIZATION
SHOW_AVERAGE_CO2
```

---

# Paramètres de calcul

## Roulements analysés

```python
SELECTED_BEARINGS
```

---

## Sensibilité sur α

```python
ALPHA_VALUES
```

---

## Sensibilité sur β

```python
BETA_VALUES
```

---

## Résolution numérique

```python
N_INTEGRATION_POINTS
```

Augmenter cette valeur améliore la précision mais augmente le temps de calcul.

---

# Résultats obtenus

Les simulations réalisées montrent :

- des durées de vie L10 largement supérieures à la durée de vie du véhicule ;
- une forte influence du paramètre α ;
- une influence plus modérée mais significative du paramètre β ;
- un remplacement optimal dépendant principalement de l'hypothèse d'usure retenue ;
- dans le cas nominal, le remplacement préventif n'est généralement pas nécessaire avant la fin de vie du véhicule.

---

# Améliorations futures

- ajout d'une interface utilisateur console ;
- ajout d'une interface graphique ;
- prise en compte détaillée de la relubrification ;
- prise en compte du recyclage des matériaux ;
- ajout d'autres familles de roulements ;
- intégration dans un futur Digital Twin MULO.