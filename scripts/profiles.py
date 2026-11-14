"""
Hand-written profiles for the Compare view, summarised from each
investigation's PSI description (approach, hardware, experimental table).

hardware: where and with what apparatus it ran
fuel:     what burned, and the sample/burner shape and size
measured: sensors and the quantities recorded
"""

ACME = "ACME burner hardware in the Combustion Integrated Rack (CIR), ISS"
MDCA = "Multi-user Droplet Combustion Apparatus (MDCA) in the CIR, ISS"
MSG_DUCT = "Fan-driven flow duct (built for SPICE) in the Microgravity Science Glovebox, ISS"
SAFFIRE = "Large flow duct in a Cygnus cargo ship, run after it left the ISS"

PROFILES = {
    "PSI-10": {
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
        "hardware": ACME,
        "fuel": "Propane, butane, pentane and ethane from a spherical burner; inverse flames used up to 85% oxygen",
        "measured": "Cameras, radiometers, photomultiplier tubes, thermocouples; cool-flame and hot-flame behaviour",
    },
    "PSI-39": {
        "hardware": MDCA,
        "fuel": "Free-floating or fiber-tethered droplets of n-dodecane, farnesane and dodecane/iso-dodecane mixes",
        "measured": "Black-and-white camera (droplet size), UV camera (OH* emission, flame size)",
    },
    "PSI-68": {
        "hardware": MDCA,
        "fuel": "Liquid droplets 1.5 to 5 mm: iso-octane, n-octane, heptane and mixtures, in O₂/N₂ or O₂/He",
        "measured": "Droplet and flame diameter over time, extinction",
    },
    "PSI-69": {
        "hardware": MDCA,
        "fuel": "Liquid droplets about 1.5 to 4 mm: methanol and heptane, some with CO₂ or helium added",
        "measured": "Droplet diameter, flame extinction diameter, burning rate, burn time; limiting oxygen index",
    },
    "PSI-26": {
        "hardware": MSG_DUCT,
        "fuel": "Cotton-fiberglass fabric (SIBAL), Nomex and PMMA plastic as 1 to 2 cm strips, slabs and spheres; wax candles",
        "measured": "Top and edge video: flame size, shape, colour, spread rate, quenching; nitrogen suppression",
    },
    "PSI-25": {
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
