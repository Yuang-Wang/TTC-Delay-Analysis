-- 1. Top 10 routes by delay count
SELECT
    route_line,
    mode,
    COUNT(*) AS delay_records,
    ROUND(AVG(min_delay), 2) AS avg_delay_minutes,
    SUM(min_delay) AS total_delay_minutes
FROM ttc_delay_cleaned
GROUP BY route_line, mode
ORDER BY delay_records DESC
LIMIT 10;


-- 2. Top 10 locations by delay count
SELECT
    location,
    mode,
    COUNT(*) AS delay_records,
    ROUND(AVG(min_delay), 2) AS avg_delay_minutes,
    SUM(min_delay) AS total_delay_minutes
FROM ttc_delay_cleaned
GROUP BY location, mode
ORDER BY delay_records DESC
LIMIT 10;


-- 3. Top 10 incident descriptions by delay count
SELECT
    incident_description,
    incident_category,
    COUNT(*) AS delay_records,
    ROUND(AVG(min_delay), 2) AS avg_delay_minutes,
    SUM(min_delay) AS total_delay_minutes
FROM ttc_delay_cleaned
WHERE incident_description <> 'Unknown'
GROUP BY incident_description, incident_category
ORDER BY delay_records DESC
LIMIT 10;


-- 4. Top 10 incident descriptions by total delay minutes
SELECT
    incident_description,
    incident_category,
    COUNT(*) AS delay_records,
    ROUND(AVG(min_delay), 2) AS avg_delay_minutes,
    SUM(min_delay) AS total_delay_minutes
FROM ttc_delay_cleaned
WHERE incident_description <> 'Unknown'
GROUP BY incident_description, incident_category
ORDER BY total_delay_minutes DESC
LIMIT 10;


-- 5. Delay records by time period
SELECT
    time_period,
    COUNT(*) AS delay_records,
    ROUND(AVG(min_delay), 2) AS avg_delay_minutes,
    SUM(min_delay) AS total_delay_minutes
FROM ttc_delay_cleaned
GROUP BY time_period
ORDER BY delay_records DESC;