import pandas as pd
from itertools import chain
from collections import defaultdict

BIODIESEL = "Biodiesel B25.5 (25% inblandning av FAME/HVO)"
BIOBENSIN = "Biobensin E4.8 (4.8% bioinblandning)"
DIESEL = "Konventionell diesel"
BENSIN = "Konventionell bensin"
ELFORDON_17 = "Elfordon. 17 kWh"

car_cats = {
    "service": {
        "small": ["VW CADDY", "VW TRANSPORT"],
        "medium": ["MB VITO", "VW TRANSPORTER"],
        "big": ["MB SPRINTER", "VW CRAFTER"],
    },
    "work": [
        "AUDI A6",
        "AUDI Q5",
        "BMW 220D",
        "BMW 318D",
        "BMW 320D",
        "SKODA SUPERB",
        "VOLVO S60",
        "VOLVO S90",
        "VOLVO V60",
        "VOLVO V90",
        "VOLVO XC40",
        "VOLVO XC60",
        "VOLVO XC70",
        "VW PASSAT",
        "VW TIGUAN",
        "VW TOUAREG",
    ],
}

service_brands = set(chain(*car_cats["service"].values()))
work_brands = set(car_cats["work"])


def write_excel(file_name: str, sheets):
    writer = pd.ExcelWriter(f"{file_name}.xlsx")
    [df.to_excel(writer, sheet) for sheet, df in sheets.items()]
    writer.save()


def read_csv(file_name: str, **args: dict) -> pd.DataFrame:
    return pd.read_csv(filepath_or_buffer=file_name, **args)


def file_name_suffix(name: str) -> str:
    return name[name.rfind("_") + 1 : -4]


def scen1_a(totals, df_cars):
    df = df_cars.query("(brand in @service_brands & year < 2015) | (brand in @work_brands & year < 2017)")
    return totals, df


# Remove biodiesel from all
def scen1_b(totals, df_cars):
    d = {}
    _, df_cars = scen1_a(totals, df_cars)
    for cat, df in totals.items():
        remaining = df.drop(df[((df["fuel"] == BIODIESEL) | (df["fuel"] == BIOBENSIN))].index)
        d[cat] = remaining
    return d, df_cars


def scen1_c(totals, df_cars):
    # Samma som scenario 1, men räkna med svensk elmix.
    elmixes = {
        "small": {"Elfordon skåp. 26.7 kWh": 11656},
        "work": {"Elfordon. 39 kWh": 13647, "Elfordon. 17 kWh": 9785, "Elfordon. 100 kWh": 24366, "Laddhybrid": 12031},
    }
    _, df_cars = scen1_a(totals, df_cars)
    for cat, df in totals.items():
        if cat not in elmixes:
            continue
        for fuel, val in elmixes[cat].items():
            df.loc[df["fuel"].str.contains(fuel), "co2"] = val

    return totals, df_cars


def scen1_d(totals, df_cars):
    # Samma som scenario 1, men räkna med europeisk elmix.
    elmixes = {
        "small": {"Elfordon skåp. 26.7 kWh": 21740},
        "work": {"Elfordon. 39 kWh": 17194, "Elfordon. 17 kWh": 12846, "Elfordon. 100 kWh": 29712, "Laddhybrid": 15439},
    }
    _, df_cars = scen1_a(totals, df_cars)
    for cat, df in totals.items():
        if cat not in elmixes:
            continue
        for fuel, val in elmixes[cat].items():
            df.loc[df["fuel"].str.contains(fuel), "co2"] = val

    return totals, df_cars


def scen2(totals, df_cars):
    # Byt färre fordon, sätt mängden utbytta fordon till 10% => 28 av 282.
    sorted_cars = df_cars.sort_values(by=["co2"], ascending=False)
    return totals, sorted_cars.iloc[: len(sorted_cars) // 10, :]


def scen3(totals, df_cars):
    d = {}
    _, df_cars = scen1_a(totals, df_cars)
    for cat, df in totals.items():
        d[cat] = df[(df["fuel"] == BENSIN) | (df["fuel"] == DIESEL)]
    return d, df_cars


def scen4(totals, df_cars):
    # Byt samtliga fordon, även om leasingperioden inte utgått, förutsatt att det finns alternativ som har lägre utsläppsvärden. Därmed ej tillämpbart på företaget men ger en mer allmän teoretisk tillämpning.
    return totals, df_cars


def scen6_a(totals, df_cars):
    _, df_cars = scen1_a(totals, df_cars)
    return totals, df_cars


def scen6_b(totals, df_cars):
    _, df_cars = scen1_a(totals, df_cars)
    return totals, df_cars


def copy_df_totals(df_totals):
    d = {}
    for cat, df in df_totals.items():
        d[cat] = df.copy()
    return d


def filter_better_co2(df, cat_co2_dict):
    b = pd.DataFrame()
    for cat, co2 in cat_co2_dict.items():
        a = (df["category"] == cat) & (df["co2"] > co2)
        b = b.append(df[a == True])
    return b.sort_index()


# Find best fuel value for every category
def find_opt_co2(scen, df_cars, df_totals):
    cat_co2_dict = {}
    co2_fuel_dict = {}
    totals, cars = copy_df_totals(df_totals), df_cars.copy()
    d, df_cars = scen(totals, cars)
    for cat, df in d.items():
        min_idx = df["co2"].idxmin()
        fuel, co2 = df.loc[min_idx].values
        cat_co2_dict[cat] = co2
        co2_fuel_dict[co2] = fuel
    return df_cars, cat_co2_dict, co2_fuel_dict


def get_car_cat(brand):
    if brand in work_brands:
        return "work"
    for k, v in car_cats["service"].items():
        if brand in set(v):
            return k
    raise Exception(f"Could not classify brand {brand}")


def optimize_big(df, cat_co2_dict):
    # Only replace if medium is better than big
    if cat_co2_dict["big"] < cat_co2_dict["medium"]:
        return df, pd.DataFrame()
    candidates = df.query("category == 'big' & (region == 'ÖST' | region == 'SYD' | region == 'VÄST')").sort_values(
        "co2", ascending=False
    )
    candidates = candidates.iloc[: len(candidates) // 4]
    df_replaced = df.copy()
    df_replaced.loc[candidates.index, "category"] = "medium"
    return df_replaced, candidates


def find_best_fuels(df, cat_co2_dict, co2_fuel_dict):
    df = filter_better_co2(df, cat_co2_dict)
    df, big_replaced = optimize_big(df, cat_co2_dict)
    df = df.assign(new_co2=[cat_co2_dict[cat] for cat in df["category"]])
    df = df.assign(new_fuel=[co2_fuel_dict.get(co2, None) for co2 in df["new_co2"]])
    return df, big_replaced


def assign_costs(name, df):
    copy = df.copy()
    for type_, dict_ in df_costs.items():
        for cat, cost_df in dict_.items():
            c = df_costs[type_][cat]
            a = df[(df["category"] == cat)]
            new_col = f"{type_}_cost"
            if new_col == "new_fuel_cost" and name in cost_scenarios:
                continue
            b = a.join(c.set_index(type_), on=type_)["cost"]
            if new_col in copy.columns:
                b = b.rename(new_col)
                copy.update(b)
            else:
                copy = copy.assign(**{new_col: b})
    return copy


def run_scenarios(scenarios, df_cars, df_totals):
    sheets = {}
    for scen in scenarios:
        name = scen.__name__
        print(name)
        df, big_replaced = find_best_fuels(*find_opt_co2(scen, df_cars, df_totals))
        df = assign_costs(name, df)
        df.loc[big_replaced.index, "category"] = "big"  # Show the 25% cars as big again
        if name in cost_scenarios:
            df = run_cost_scenario(name, df)
        df = df_cars.combine_first(df)
        df = assign_costs(name, df)
        sheets[name] = df
    return sheets


def fuel_to_co2():
    d = defaultdict(dict)
    for cat, df in df_totals.items():
        for index, row in df.iterrows():
            d[cat][row["fuel"]] = row["co2"]
    return d


def scen6_a_fuel_costs(fuel_dict):
    return fuel_dict


def scen6_b_fuel_costs(fuel_dict):
    d = {}
    for cat, df in fuel_dict.items():
        d[cat] = df[df["new_fuel"] != ELFORDON_17]
    return d


def min_fuel_cost(df):
    min_idx = df["cost"].idxmin()
    return df.iloc[min_idx]


def run_cost_scenario(scen, df):
    fuel_co2_dict = fuel_to_co2()
    copy = df.copy()
    copy.loc[:, "new_fuel_cost"] = None
    fuel_dict = globals()[f"{scen}_fuel_costs"](df_costs["new_fuel"])
    for cat, df_cost in fuel_dict.items():
        min_fuel, min_val = min_fuel_cost(df_cost)
        if cat == "big":
            f2, c2 = min_fuel_cost(fuel_dict["medium"])
            if c2 < min_val:
                top25 = copy[
                    (copy["category"] == "big")
                    & (copy["brand_cost"] > c2)
                    & ((copy["region"] == "SYD") | (copy["region"] == "VÄST") | (copy["region"] == "ÖST"))
                ].sort_values("brand_cost", ascending=False)
                top25 = top25.iloc[: len(top25) // 4].index
                rest = copy[(copy["category"] == cat) & (copy["brand_cost"] > min_val)].index
                copy.loc[rest, "new_fuel_cost"] = min_val
                copy.loc[top25, "new_fuel_cost"] = c2
                copy.loc[rest, "new_cost_fuel"] = min_fuel
                copy.loc[top25, "new_cost_fuel"] = f2
                copy.loc[rest, "new_cost_fuel_co2"] = fuel_co2_dict[cat][min_fuel]
                copy.loc[top25, "new_cost_fuel_co2"] = fuel_co2_dict[cat][f2]
        else:
            a = copy[(copy["category"] == cat) & (copy["brand_cost"] > min_val)]
            copy.loc[a.index, "new_fuel_cost"] = min_val
            copy.loc[a.index, "new_cost_fuel"] = min_fuel
            copy.loc[a.index, "new_cost_fuel_co2"] = fuel_co2_dict[cat][min_fuel]
    return copy


def read_totals():
    total_names = ["fuel", "co2"]
    return {
        file_name_suffix(name): read_csv(file_name=name, encoding="utf-8", names=total_names, header=0)
        for name in total_csvs
    }


def read_costs():
    df_costs = defaultdict(dict)

    for csv in costs_csvs:
        type_, cat = csv[:-4].split("_")
        col = type_ if type_ == "brand" else f"new_{type_}"
        df = read_csv(file_name=f"kostnader/{csv}", names=[col, "cost"], header=0)
        if type_ == "brand":
            df[type_] = df[type_].str.upper()
        df_costs[col][cat] = df
    return df_costs


def read_cars():
    df_new_co2 = read_csv(file_name="fordonspark.csv", encoding="utf-8", header=0, names=["license_nbr", "co2"])
    df_cars = pd.read_csv(
        "cars.csv",
        encoding="latin1",
        sep=";",
        header=0,
        names=["license_nbr", "brand", "year", "driver", "region", "consumption", "co2", "fuel"],
    )
    df_cars["brand"] = df_cars["brand"].apply(lambda b: " ".join(b.upper().split(" ")[:2]))
    df_cars = df_cars.assign(category=[get_car_cat(brand) for brand in df_cars["brand"]])
    df_cars["co2"] = df_new_co2["co2"]
    return df_cars


if __name__ == "__main__":
    total_csvs = ["total_service_big.csv", "total_service_medium.csv", "total_service_small.csv", "total_work.csv"]
    costs_csvs = [
        "brand_big.csv",
        "brand_small.csv",
        "fuel_big.csv",
        "fuel_small.csv",
        "brand_medium.csv",
        "brand_work.csv",
        "fuel_medium.csv",
        "fuel_work.csv",
    ]
    df_totals = read_totals()
    df_costs = read_costs()
    df_cars = read_cars()

    cost_scenarios = {"scen6_a", "scen6_b"}
    scenarios = [scen1_a, scen1_b, scen1_c, scen1_d, scen2, scen3, scen4, scen6_a, scen6_b]
    sheets = run_scenarios(scenarios, df_cars, df_totals)
    write_excel("isak", sheets)
