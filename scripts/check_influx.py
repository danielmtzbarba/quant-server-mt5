from influxdb_client import InfluxDBClient

# Minimal config to match sync_service
INFLUX_URL = "http://localhost:8086"
INFLUX_TOKEN = "X3jsB_yeGU3Il5BINWNYNicYDQ7dkhjbG4PHUAN6yt9XuJHaN8Bj7ROyQr81h-Vwh3Qw6qHNMLF2wylXdaEnFQ=="
INFLUX_ORG = "danielmtz"
INFLUX_BUCKET = "tradedb"


def check_db():
    client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
    query_api = client.query_api()

    flux_query = f"""
    from(bucket: "{INFLUX_BUCKET}")
      |> range(start: -7d)
      |> filter(fn: (r) => r["_measurement"] == "market_data")
      |> count()
    """
    try:
        result = query_api.query(flux_query)
        print("--- InfluxDB Record Count (Last 7 Days) ---")
        for table in result:
            for record in table.records:
                print(
                    f"Symbol: {record.values.get('symbol')}, Field: {record.get_field()}, Count: {record.get_value()}"
                )

        # Get latest 5 points
        flux_query_latest = f"""
        from(bucket: "{INFLUX_BUCKET}")
          |> range(start: -7d)
          |> filter(fn: (r) => r["_measurement"] == "market_data")
          |> last()
        """
        result_latest = query_api.query(flux_query_latest)
        print("\n--- Latest Records ---")
        for table in result_latest:
            for record in table.records:
                print(
                    f"Time: {record.get_time()}, Symbol: {record.values.get('symbol')}, Field: {record.get_field()}, Value: {record.get_value()}"
                )

    except Exception as e:
        print(f"Error querying InfluxDB: {e}")
    finally:
        client.close()


if __name__ == "__main__":
    check_db()
