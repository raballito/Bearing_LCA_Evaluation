<<<<<<< HEAD
# Bearing_LCA_Evaluation
LCA Evaluation pour bearing in a light vehicle
=======
# MULO – Optimisation de la durée de vie des roulements

## Objectif du projet

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

Les efforts appliqués au roulement sont définis dans :

```text
loads/
```

Chaque scénario contient :

- Fx
- Fy
- Fz

Le programme calcule ensuite automatiquement :

```text
Fr = sqrt(Fx² + Fz²)

Fa = abs(Fy)
```

---

## 2. Modèle de frottement

Le couple de frottement est obtenu à partir :

```text
friction/*.*lsx
``*

Les données proviennent du calcu*ateur SKF.

Une interpolation 3D e*t réalisée selon :

```text
Fr
Fa
*PM
```

Le modèle*retourne :

```text
Moment*de frottement [N.m]
```

*--

## 3. Charge*dynamique équivalente SKF

Pour le**roulements supportant les*efforts axiaux :

```text
P = Fr
`*`

si :

```text
Fa/Fr ≤*e
```

Sinon*:

```text
P = X·Fr +*Y·Fa
```

Les coefficients :

-*e
- X
- Y

sont*interpolés depuis :

```text
SKF_B*aring*Coef.xlsx
```

en*fonction du paramètre SKF*:

```text
f0·Fa/C0*```

---

## 4. Durée*de vie L10

La durée de vie nomina** est calculée selon*:

```math
L10=*C/P)^p·10^6
```

avec :

### Roule*ents à billes*
```text
p = 3
```

### Roulements*à rouleaux

```text*p = 10/3
```

*e résultat est obtenu en :

- tour*
- kilomètres

*--

##*5. Modèle d'usure

Le*modèle utilise la*loi :

```math
M =*M0·(1 + α*(N/L10)^β)
```

*vec :

| Paramètre |*Signification |
|------------*------------|
| M0 |*Couple du roulement neuf |
| N | N*mbre de tours réalisés*|
|*L10 |*Durée de vie nominale |
| α | Ampl*tude de la dégradation |
| β | For*e de la dégradation |

---

# Hypo*hèses principales*
## Hypothèse 1 – Profil d*utilisation

Le véhicule n'est pas*utilisé dans un seul état de charg*.

Un profil de conduite est défin* :

*``python
USAGE_PROFILE = {
    "*oulage": 0.70,
    "*cceleration_max": 0.15,
   *"freinage_max": 0.15*}
```

La somme des poids doit êtr* égale*à :

```text
1.0*```

---

## Hypothèse 2 – Vieilli*sement

*ucune loi de*vieillissement spécifique au*roulement n'a été ident*fiée dans la littérature.

Le viei*l*ssement est donc représenté par*:

```math
M =*M0·(1 + α·(N*L10)^β)
*``

### α

Contrôle l'amplitude de*l'usure.

Valeur*nominale :

```text
α =*0.5
```

Valeurs étudi*es :

```text
0.5
2
5
10
*0
```

---

### β

Contrôle*la forme de la dégradation.

Vale*r nominale :

```text
β = *
```

Interprétation :

| β*| Interprétation |
|------*------|
| β < 1 | Usure précoce*|
| β = 1 | Usure liné*ire |
| β = 2 | Usure*progressive |
| β > 2 | Usure*retardée |

Valeurs étudiées :

``**ext
0.5
1
2
*
4
```

---

## Hyp*thèse 3 – Électricité

Facteur d*émission utilisé :

```text
90 gCO**kWh
```

Rendement*global :

```text
50 %
```

D*où :

```text
180 gCO₂/k*h utile
```

---

## Hyp*thèse 4 – Transport

Vale*rs d'ordre de grandeur :

###*SKF 6307

```text
40 g*O₂
```

### SKF NU2206*
```text
30 gCO₂
``*

---

## Hypothèse 5 – Fin de vie*
Act*ellement :

```text
0 gCO₂
*``

Le recyclage de l'acier n'est *as explicitement valorisé.

---

#* Hypothèse 6 – Maintenance

Act*ellement :

```text
0 gCO₂
```

Un**valeur indicative de :

```text
*0 gCO₂
```

par relubrification pe*t être utilisée lors*de futures études.

---

# Configu*ation du véhicule

Modifier :

```*ext
vehicle.json
*``

Exemple :

```json
{
 *"wheel_radius_m": 0.253,
* "vehicle_avg_speed_kmh": 30*
  "vehicle_max_speed_kmh": *0,
  "electricity_co2_g_per_kwh": *0,
* "grid_to*wheel_efficiency": 0.5,
* "vehicle_lifetime_km": 100*000
}
```

---

# Configuration d*un roulement

Exemple :

```json
{*  "name": "SKF 6307*2RS1",

  "position": "*ear",

  "quantity": *,

  "mass_kg": 0*458,

  "bearing_type": "ball*,

  "supports_axial_load": true,
*  "f*": 13.1*

  "dynamic_capacity_N": 49300*

  "static_capacity_N*: 19000,

 *"speed_limit_rpm": 10000,

  "manu*acturing_co2_g": 1700,

  "distrib*tion_co2_g": 40,

  "end_of_life_c*2_g": 0,

  "maintenance_co2_g": 0*

  "maintenance_interval_rev": nu*l,

  "friction_file": "./friction*SKF_6307_2RS1.xlsx",

  "loads_fil*": "./loads/SKF_6307_2RS1_loads.js*n"
}
```

---

# Ajouter un nouvea* roulement

## Étape 1

Créer :

`*`text
bearings/NouveauRoulement.js*n
```

---

## Ét*pe 2

Créer :

```text
fr*ction/NouveauRoulement.xlsx
```

a*ec*les colonnes :

```text
Force Radi*le*[N]
Force Axiale [N]
200*RPM
315 RPM
...
```

---

## Étape*3

Créer :

```*ext
loads/NouveauRoulement_loads.j*on
``*

---

## Étape 4

Ajouter son*nom dans :

```python
SELECTED_BEA**NGS
```

Le*programme le prendra automatiqueme*t*en compte.

---

# Graphiques disp*nibles

Les graphi*ues sont activés via les interrupt*urs :

```python
SHOW_FRICTION
SHO*_ALPHA_SENSITIVITY
SHOW_CO2_EV*LUTION
SHOW_OPTIMIZATION
SHOW_AVER*GE_CO2
```

---

# Paramètres de c*lcul

## Roulements analysés

```*ython
SELECTED_B*ARINGS
```

---

## Sensibilité su* α

```python
ALPHA_VALUES
```

--*

## Sensibilité sur β

```python
*ETA_VALUES
```

---

## Rés*lution numérique

```python
*_INTEGRATION_POINTS
```

Aug*enter cette valeur améliore la pré*ision*mais augmente le temps de*calcul.

---

# Résultats*obtenus

Les simulations réalisées*montrent :

-*des durées de vie L10*largement supérieures à la durée d**vie du*véhicule*;
- une forte influence*du paramètre α*;
- une influence plus modérée mai* significative du param*tre β ;
- un remplacement optimal*dépendant principalement de l'hypo*hèse d*usure retenue ;
- dans le cas nomi*al, le remplacement préventif n'es* généralement*pas nécessaire avant la fin de*vie du véhicule.

---

# Améliorat*ons futures

- ajout d'une interfa*e utilisateur console ;
- ajout d'*ne interface graphique ;
- prise e* compte détaillée de la relubrific*tion ;
- prise en compte du recycl*ge des matériaux ;
- ajout d'autre* familles de roulements ;
- intégr*tion dans un futur Digital Twin MU*O.
>>>>>>> c2f13c4 (First Release)
