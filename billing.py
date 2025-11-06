# --- Billing Constants ---
FIXED_CHARGE_SINGLE_PHASE = 115.00
WHEELING_CHARGE_PER_KWH = 1.40
FAC_PER_KWH = 0.00
ELECTRICITY_DUTY_RATE = 0.16
slabs = [
    (100, 3.46),  # 0-100 kWh (width 100)
    (200, 7.43),  # 101-300 kWh (width 200)
    (200, 10.32), # 301-500 kWh (width 200)
    (500, 11.71), # 501-1000 kWh (width 500)
    (float('inf'), 11.71) # >1000 kWh (infinite width)
]

# --- THIS IS THE MISSING FUNCTION ---
def calculate_mahadiscom_bill(kwh_units):
    """
    Calculates an estimated MSEDCL bill based on a telescopic tariff.
    """
    bill = {}
    bill_details = []
    energy_charge = 0.0
    remaining_units = kwh_units
    
    slab_labels = [
        "  - 0-100 kWh:",
        "  - 101-300 kWh:",
        "  - 301-500 kWh:",
        "  - 501-1000 kWh:",
        "  - >1000 kWh:"
    ]
    
    for i, (slab_width, rate) in enumerate(slabs):
        if remaining_units <= 0:
            break
            
        units_in_this_slab = min(remaining_units, slab_width)
        slab_cost = units_in_this_slab * rate
        energy_charge += slab_cost
        remaining_units -= units_in_this_slab
        
        label = slab_labels[i] if i < len(slab_labels) else "  - Other:"
        bill_details.append(f"{label} {units_in_this_slab:>6.2f} kWh @ ₹{rate:.2f}/unit = ₹{slab_cost:.2f}")

    bill['A_Energy_Charge'] = energy_charge
    bill['B_Fixed_Charge'] = FIXED_CHARGE_SINGLE_PHASE
    bill['C_Wheeling_Charge'] = kwh_units * WHEELING_CHARGE_PER_KWH
    bill['D_FAC'] = kwh_units * FAC_PER_KWH
    sub_total = (bill['A_Energy_Charge'] + bill['B_Fixed_Charge'] + 
                 bill['C_Wheeling_Charge'] + bill['D_FAC'])
    bill['E_Electricity_Duty'] = sub_total * ELECTRICITY_DUTY_RATE
    bill['F_Total_Bill'] = sub_total + bill['E_Electricity_Duty']
    
    return bill, bill_details