# CSV Import Templates

## Weather Station CSV Template

Use this template for importing weather stations. You can use either latitude/longitude values OR provide a location in Well-Known Text (WKT) format.

### Option 1: Using latitude and longitude fields:

```csv
name,latitude,longitude,description,altitude,is_active,date_installed
"Central Station",35.6895,139.6917,"Main monitoring station",45.5,true,2023-01-15
"Mountain Peak",-33.8688,151.2093,"High altitude station",1200.3,true,2022-11-20
"Coastal Point",37.7749,-122.4194,"Sea level monitoring",5.2,false,2023-03-01
```

### Option 2: Using location field in WKT format:

```csv
name,location,description,altitude,is_active,date_installed
"Central Station","POINT(139.6917 35.6895)","Main monitoring station",45.5,true,2023-01-15
"Mountain Peak","POINT(151.2093 -33.8688)","High altitude station",1200.3,true,2022-11-20
"Coastal Point","POINT(-122.4194 37.7749)","Sea level monitoring",5.2,false,2023-03-01
```

### Option 3: Using simple coordinates format:

```csv
name,location,description,altitude,is_active,date_installed
"Central Station","139.6917,35.6895","Main monitoring station",45.5,true,2023-01-15
"Mountain Peak","151.2093,-33.8688","High altitude station",1200.3,true,2022-11-20
"Coastal Point","-122.4194,37.7749","Sea level monitoring",5.2,false,2023-03-01
```

## Climate Data CSV Template

For climate data imports, you can reference stations by name or ID:

### Option 1: Reference by station name:

```csv
station_name,timestamp,temperature,humidity,precipitation,wind_speed,wind_direction,barometric_pressure,data_quality
"Central Station","2023-05-01T12:00:00",23.5,65.2,0.0,12.3,180,1013.2,high
"Mountain Peak","2023-05-01T12:00:00",12.1,82.0,1.5,25.7,270,890.3,medium
"Coastal Point","2023-05-01T12:00:00",18.9,75.5,0.2,8.2,90,1011.8,high
```

### Option 2: Reference by station ID:

```csv
station_id,timestamp,temperature,humidity,precipitation,wind_speed,wind_direction,barometric_pressure,data_quality
1,"2023-05-01T12:00:00",23.5,65.2,0.0,12.3,180,1013.2,high
2,"2023-05-01T12:00:00",12.1,82.0,1.5,25.7,270,890.3,medium
3,"2023-05-01T12:00:00",18.9,75.5,0.2,8.2,90,1011.8,high
```

## Notes on CSV Formatting:

1. The first row must contain column headers
2. Text values with commas should be enclosed in quotes
3. Date format should be ISO standard: YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS
4. Numeric values should use period (.) as decimal separator
5. Boolean values can be: true/false, yes/no, 1/0, t/f, y/n (case insensitive)
6. For point locations, remember longitude comes first, then latitude