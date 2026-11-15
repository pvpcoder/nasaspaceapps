"""
Hand-written profiles for the Compare view, summarised from each
investigation's PSI description (approach, hardware, experimental table).

hardware: where and with what apparatus it ran
fuel:     what burned, and the sample/burner shape and size
measured: sensors and the quantities recorded
agents:   suppressants or diluent gases used (optional)
airflow_note: shown when airflow exists but isn't in clear units (optional)
"""

ACME = "ACME burner hardware in the Combustion Integrated Rack (CIR), ISS"
MDCA = "Multi-user Droplet Combustion Apparatus (MDCA) in the CIR, ISS"
MSG_DUCT = "Fan-driven flow duct (built for SPICE) in the Microgravity Science Glovebox, ISS"
SAFFIRE = "Large flow duct in a Cygnus cargo ship, run after it left the ISS"

PROFILES = {
    "PSI-10": {
        "agents": "Nitrogen as diluent",
        "hardware": ACME,
        "fuel": "Gaseous ethylene from a porous spherical burner; normal flames (fuel flows out) and inverse flames (oxygen flows out)",
        "measured": "Cameras, radiometers, photomultiplier tubes, thermocouples; soot-inception limits",
    },
    "PSI-20": {
        "hardware": ACME,
        "fuel": "Ethylene or methane through a flat porous burner (25 or 50 mm) built to imitate a burning solid",
        "measured": "Heat-flux sensor, burner surface temperature, cameras; a flammability map in still air",
    },
    "PSI-21": {
        "hardware": ACME,
        "fuel": "Methane and ethylene jet flames with a surrounding (coflow) air stream",
        "measured": "OH* and CH* chemiluminescence, soot luminosity, laser extinction, thin-filament pyrometry",
    },
    "PSI-22": {
        "hardware": ACME,
        "fuel": "Gas-jet and coflow flames under an electric field of up to 10 kV (mimics partial gravity)",
        "measured": "Ion current through the flame, flame response to the field, cameras",
    },
    "PSI-23": {
        "hardware": ACME,
        "fuel": "Hydrogen, methane and ethylene from a spherical porous burner",
        "measured": "Spectrally resolved images, flame and burner temperatures, radiative flux",
    },
    "PSI-159": {
        "agents": "Nitrogen as diluent",
        "hardware": ACME,
        "fuel": "Propane, butane, pentane and ethane from a spherical burner; inverse flames used up to 85% oxygen",
        "measured": "Cameras, radiometers, photomultiplier tubes, thermocouples; cool-flame and hot-flame behaviour",
    },
    "PSI-39": {
        "agents": "Nitrogen and helium as diluents",
        "hardware": MDCA,
        "fuel": "Free-floating or fiber-tethered droplets of n-dodecane, farnesane and dodecane/iso-dodecane mixes",
        "measured": "Black-and-white camera (droplet size), UV camera (OH* emission, flame size)",
    },
    "PSI-68": {
        "agents": "Helium or nitrogen as the diluent gas (O₂/He or O₂/N₂ atmospheres)",
        "hardware": MDCA,
        "fuel": "Liquid droplets 1.5 to 5 mm: iso-octane, n-octane, heptane and mixtures, in O₂/N₂ or O₂/He",
        "measured": "Droplet and flame diameter over time, extinction",
    },
    "PSI-69": {
        "agents": "CO₂ and helium added to the chamber atmosphere to test suppression; nitrogen as the usual diluent",
        "hardware": MDCA,
        "fuel": "Liquid droplets about 1.5 to 4 mm: methanol and heptane, some with CO₂ or helium added",
        "measured": "Droplet diameter, flame extinction diameter, burning rate, burn time; limiting oxygen index",
    },
    "PSI-26": {
        "agents": "Nitrogen released to extinguish flames (similar to the ISS extinguishing approach)",
        "hardware": MSG_DUCT,
        "fuel": "Cotton-fiberglass fabric (SIBAL), Nomex and PMMA plastic as 1 to 2 cm strips, slabs and spheres; wax candles",
        "measured": "Top and edge video: flame size, shape, colour, spread rate, quenching; nitrogen suppression",
    },
    "PSI-25": {
        "agents": "Nitrogen added to lower oxygen below 21%", "airflow_note": "Recorded as fan and air-speed settings; units unclear (up to 40 cm/s per NASA's description)",
        "hardware": MSG_DUCT,
        "fuel": "SIBAL fabric strips (1 to 2 cm), PMMA rods (1/4 to 1/2 inch) and thin PMMA films, Nomex",
        "measured": "Flame growth and spread rate, radiometer, O₂, CO₂ and CO before and after each burn",
    },
    "PSI-106": {
        "hardware": MSG_DUCT,
        "fuel": "Coflow jet flames: methane, ethylene, ethane and nitrogen-diluted mixes",
        "measured": "4,000+ high-resolution images, flow rates, temperatures; flame liftoff and stability",
    },
    "PSI-107": {
        "hardware": MSG_DUCT,
        "fuel": "Coflow jet flames from 0.41, 0.76 and 1.6 mm nozzles: methane, ethylene, propane, propylene",
        "measured": "Flame length, smoke point (when soot appears), radiative loss, coflow velocity",
    },
    "PSI-98": {
        "hardware": SAFFIRE,
        "fuel": "One large cotton-fiberglass fabric (SIBAL) sample, 94 × 40 cm",
        "measured": "Two cameras, thermocouples, radiometers, O₂, CO₂ and pressure sensors",
    },
    "PSI-99": {
        "hardware": SAFFIRE,
        "fuel": "Nine 5 × 29 cm samples: SIBAL fabric, silicone, flat and structural PMMA, PMMA with Nomex",
        "measured": "Two cameras, thermocouples, radiometers, O₂ and CO₂ sensors; burn length in space vs on Earth",
    },
    "PSI-100": {
        "hardware": SAFFIRE,
        "fuel": "Large SIBAL fabric samples, 94 × 40.6 cm",
        "measured": "Two cameras, thermocouples, radiometers, O₂, CO₂ and pressure sensors, anemometers",
    },
    "PSI-102": {
        "hardware": "Smoke-measurement hardware in the Microgravity Science Glovebox, ISS",
        "fuel": "Heated (smouldering, not flaming) spacecraft materials: Teflon, Kapton, silicone rubber, lampwick, dibutyl phthalate",
        "measured": "Two commercial smoke detectors, thermophoretic soot samplers (electron microscope), sample mass loss",
    },
    "PSI-101": {
        "hardware": "SAME smoke-measurement hardware in the Microgravity Science Glovebox, ISS",
        "fuel": "Heated Kapton, silicone, lampwick, Teflon and Pyrell fire-retardant foam",
        "measured": "Smoke particle size (DustTrak, ionization detector, M-pass), aging time",
    },
    "PSI-47": {
        "hardware": "Modified TSI P-Trak particle counter, compared with a DustTrak, ISS",
        "fuel": "No fire: Arizona Red Dust released from Mylar bags (tests smoke-vs-dust sensing)",
        "measured": "Airborne particle counts",
    },
    "PSI-60": {
        "hardware": "Ground study: analysis of SPICE flight images",
        "fuel": "Modeling of SPICE coflow flames (no new burns)",
        "measured": "Soot temperature and volume fraction from colour-ratio pyrometry; soot model",
    },
    "PSI-62": {
        "hardware": "Ground study: computer modeling of BASS flight results",
        "fuel": "Models of PMMA sheets, spheres and rods and wax cylinders from BASS (no new burns)",
        "measured": "Simulated flame shape, temperature and soot vs 3-D reconstructions from BASS video",
    },
    "PSI-115": {
        "hardware": "Ground study: simulation of SAME smoke tests",
        "fuel": "Smoke from heated dibutyl phthalate (no new burns)",
        "measured": "Simulated smoke particle size in Earth gravity vs microgravity",
    },
    "PSI-117": {
        "hardware": "Ground study: 3-D CFD model validated with FLEX data",
        "fuel": "Models of n-alkane droplet cool flames, 0.5 to 4 mm (no new burns)",
        "measured": "Simulated ignition delay, flame oscillation, extinction under heat and flow disturbances",
    },
    "PSI-142": {
        "hardware": "Ground study: lab counterflow burner and numerical models using FLEX conditions",
        "fuel": "n-heptane and dimethyl ether flames, modeled up to 20 atm",
        "measured": "Cool-flame extinction limits vs oxygen concentration",
    },
}


# ---------------------------------------------------------------------------
# Connection map: hardware families, fuel shapes, photos and links.
# ---------------------------------------------------------------------------

# Experiments run on the same hardware are the most directly comparable.
FAMILIES = [
    {"key": "acme", "label": "ACME gas-flame burners",
     "where": "Combustion Integrated Rack, ISS",
     "ids": ["PSI-10", "PSI-20", "PSI-21", "PSI-22", "PSI-23", "PSI-159"]},
    {"key": "mdca", "label": "Droplet combustion apparatus (MDCA)",
     "where": "Combustion Integrated Rack, ISS",
     "ids": ["PSI-69", "PSI-68", "PSI-39"]},
    {"key": "duct", "label": "Fan-driven flow duct built for SPICE",
     "where": "Microgravity Science Glovebox, ISS",
     "ids": ["PSI-26", "PSI-25", "PSI-107", "PSI-106"]},
    {"key": "saffire", "label": "Saffire large-scale fires",
     "where": "Cygnus cargo ship, after leaving the ISS",
     "ids": ["PSI-98", "PSI-99", "PSI-100"]},
    {"key": "smoke", "label": "Smoke and dust instruments",
     "where": "Microgravity Science Glovebox and cabin, ISS",
     "ids": ["PSI-102", "PSI-101", "PSI-47"]},
    {"key": "ground", "label": "Ground studies of flight data",
     "where": "Labs and computer models on Earth",
     "ids": ["PSI-62", "PSI-60", "PSI-115", "PSI-117", "PSI-142"]},
]

# What burned, as a shape (drives the small drawing shown when there's no photo).
SHAPES = {
    "PSI-10": "sphere-burner", "PSI-20": "flat-burner", "PSI-21": "jet", "PSI-22": "jet",
    "PSI-23": "sphere-burner", "PSI-159": "sphere-burner",
    "PSI-39": "droplet", "PSI-68": "droplet", "PSI-69": "droplet",
    "PSI-25": "sheet", "PSI-26": "sheet", "PSI-106": "jet", "PSI-107": "jet",
    "PSI-98": "sheet", "PSI-99": "sheet", "PSI-100": "sheet",
    "PSI-101": "smoke", "PSI-102": "smoke", "PSI-47": "dust",
    "PSI-60": "model", "PSI-62": "model", "PSI-115": "model", "PSI-117": "model", "PSI-142": "model",
}

# NASA's representative images in PSI (only these five investigations have one).
PHOTOS = {
    "PSI-10": "PSI-10_Representative Image(s)_Flame Design_In Space flame.jpg",
    "PSI-22": "PSI-22_Representative Image(s)_E-Field Flames blue.jpg",
    "PSI-25": "PSI-25_Representative Image(s)_BASS-II_flame testing.jpg",
    "PSI-47": "PSI-47_Representative Image(s)_DAFT on ISS.jpg",
    "PSI-159": "PSI-159_Representative Image(s)_CFI-G_Observation of non-premixed quasi-steady spherical cool flames on porous burners.jpg",
}

# Short notes shown on the map.
BADGES = {
    "PSI-20": "Gas burner that imitates burning solids",
    "PSI-22": "Mimics partial gravity with an electric field",
    "PSI-159": "Highest oxygen tested: up to 85% (from the burner)",
}

# kind: series (same experiment flown again), instrument (hardware reused),
# reanalysis (ground study of flight data), emulates, related.
# source: where the link comes from.
LINKS = [
    {"from": "PSI-26", "to": "PSI-25", "kind": "series", "label": "BASS-II followed BASS", "source": "PSI metadata"},
    {"from": "PSI-69", "to": "PSI-68", "kind": "series", "label": "FLEX-2 followed FLEX", "source": "Same hardware (challenge statement)"},
    {"from": "PSI-98", "to": "PSI-99", "kind": "series", "label": "Saffire-II followed Saffire-I", "source": "PSI metadata"},
    {"from": "PSI-99", "to": "PSI-100", "kind": "series", "label": "Saffire-III followed Saffire-II", "source": "PSI metadata"},
    {"from": "PSI-102", "to": "PSI-101", "kind": "series", "label": "SAME-R reflew the SAME hardware", "source": "PSI metadata"},
    {"from": "PSI-102", "to": "PSI-47", "kind": "instrument", "label": "A SAME smoke instrument was reused to measure dust in DAFT", "source": "PSI metadata and challenge statement"},
    {"from": "PSI-20", "to": "PSI-26", "kind": "emulates", "label": "BRE's gas burner imitates burning solids like those in BASS", "source": "Challenge statement"},
    {"from": "PSI-20", "to": "PSI-98", "kind": "emulates", "label": "BRE's gas burner imitates burning solids like Saffire's fabric", "source": "Challenge statement"},
    {"from": "PSI-98", "to": "PSI-26", "kind": "related", "label": "Saffire scaled up the small-sample burns of BASS", "source": "PSI metadata"},
    {"from": "PSI-26", "to": "PSI-107", "kind": "related", "label": "BASS used the flow duct built for SPICE", "source": "PSI metadata and challenge statement"},
    {"from": "PSI-106", "to": "PSI-107", "kind": "related", "label": "SLICE used the same flow duct as SPICE", "source": "PSI metadata"},
    {"from": "PSI-22", "to": "PSI-23", "kind": "related", "label": "Both study the structure of laminar diffusion flames on ACME burners", "source": "PSI metadata"},
    {"from": "PSI-39", "to": "PSI-69", "kind": "related", "label": "CFI extended FLEX's cool-flame discovery", "source": "PSI metadata"},
    {"from": "PSI-62", "to": "PSI-26", "kind": "reanalysis", "label": "Models BASS flame spread", "source": "PSI metadata"},
    {"from": "PSI-62", "to": "PSI-25", "kind": "reanalysis", "label": "Models BASS-II flame spread", "source": "PSI metadata"},
    {"from": "PSI-60", "to": "PSI-107", "kind": "reanalysis", "label": "Re-analyses SPICE flame images", "source": "PSI metadata"},
    {"from": "PSI-115", "to": "PSI-102", "kind": "reanalysis", "label": "Simulates SAME smoke particles", "source": "PSI metadata"},
    {"from": "PSI-117", "to": "PSI-69", "kind": "reanalysis", "label": "3-D model validated with FLEX data", "source": "PSI metadata"},
    {"from": "PSI-142", "to": "PSI-69", "kind": "reanalysis", "label": "Counterflow study using FLEX conditions", "source": "PSI metadata"},
    {"from": "PSI-117", "to": "PSI-142", "kind": "related", "label": "Both model FLEX cool flames", "source": "PSI metadata"},
]
