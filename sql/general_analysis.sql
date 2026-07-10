-- 1. Total delay records
SELECT
    COUNT(*) AS total_delay_records
FROM ttc_delay_cleaned;


-- 2. Average and total delay minutes
SELECT
    ROUND(AVG(min_delay), 2) AS avg_delay_minutes,
    SUM(min_delay) AS total_delay_minutes,
    MAX(min_delay) AS max_delay_minutes
FROM ttc_delay_cleaned;


-- 3. Delay records by transit mode
SELECT
    mode,
    COUNT(*) AS delay_records,
    ROUND(AVG(min_delay), 2) AS avg_delay_minutes
FROM ttc_delay_cleaned
GROUP BY mode
ORDER BY delay_records DESC;


-- 4. Delay records by incident category
SELECT
    incident_category,
    COUNT(*) AS delay_records,
    ROUND(AVG(min_delay), 2) AS avg_delay_minutes,
    SUM(min_delay) AS total_delay_minutes
FROM ttc_delay_cleaned
GROUP BY incident_category
ORDER BY delay_records DESC;


-- 5. Mapping quality check
SELECT
    incident_mapping_status,
    COUNT(*) AS records
FROM ttc_delay_cleaned
GROUP BY incident_mapping_status
ORDER BY records DESC;