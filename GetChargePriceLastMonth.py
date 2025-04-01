from datetime import datetime, timezone, timedelta
from influxdb_client import InfluxDBClient
import calendar

# CONFIGURATION
influx_bucket = "power_metrics"
influx_org = "mads"
influx_token = "gQvFBKlyYnld9J9cVe_WlJIjzr9RP9_I0ybA7NHcdmB18varSPa7T4NfIDzKtiuosQWVfnih7KqIpaP-Y519zQ=="
influx_url = "http://192.168.0.245:8086"

# Get current date in UTC
today = datetime.now(timezone.utc)

# Determine the first and last day of the previous month
first_day_last_month = today.replace(day=1) - timedelta(days=1)
first_day_last_month = first_day_last_month.replace(day=1)
last_day_last_month = today.replace(day=1) - timedelta(days=1)

# Flux query
flux_query = f'''
// Query `power_cost` for hourly charge prices
chargePrice = from(bucket: "{influx_bucket}")
  |> range(start: time(v: "{first_day_last_month.isoformat()}"), stop: time(v: "{last_day_last_month.isoformat()}"))
  |> filter(fn: (r) => r["_measurement"] == "power_cost")
  |> filter(fn: (r) => r["_field"] == "charge_price")
  |> aggregateWindow(every: 1h, fn: mean, createEmpty: false)
  |> keep(columns: ["_time", "_value"])
  |> rename(columns: {{"_value": "charge_price"}})

// Query `Bil Opladning` for hourly energy usage
carCharging = from(bucket: "{influx_bucket}")
  |> range(start: time(v: "{first_day_last_month.isoformat()}"), stop: time(v: "{last_day_last_month.isoformat()}"))
  |> filter(fn: (r) => r["_measurement"] == "Bil Opladning")
  |> filter(fn: (r) => r["_field"] == "totalEnergy")
  |> aggregateWindow(every: 1h, fn: sum, createEmpty: false)
  |> keep(columns: ["_time", "_value"])
  |> rename(columns: {{"_value": "totalEnergy"}})

// Join the two tables on `_time`
joinedData = join(
  tables: {{price: chargePrice, energy: carCharging}},
  on: ["_time"]
)

// Multiply charge price by total energy for each time point
calculatedCost = joinedData
  |> map(fn: (r) => ({{ 
      _time: r._time, 
      _value: r.charge_price * r.totalEnergy 
    }}))

// Sum up all the calculated costs for the total price
calculatedCost
  |> group()
  |> sum(column: "_value")
  |> yield(name: "total_charge_price")
'''

# Connect to InfluxDB
client = InfluxDBClient(url=influx_url, token=influx_token, org=influx_org)
query_api = client.query_api()

try:
    result = query_api.query(org=influx_org, query=flux_query)
    total_charge_price = None
    
    for table in result:
        for record in table.records:
            total_charge_price = record.get_value()

    print(f"{total_charge_price:.2f}" if total_charge_price is not None else "0.00")

except Exception as e:
    print("0.00")  # Output a default value if an error occurs

finally:
    client.close()