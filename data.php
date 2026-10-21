<?php
declare(strict_types=1);

$dbPath = getenv('KILN_SQLITE_PATH') ?: (__DIR__ . '/data/readings.sqlite3');
$queryReadings = static function () use ($dbPath): array {
    if (!is_file($dbPath)) {
        return ['readings' => [], 'minutes' => [], 'latest' => null];
    }

    $db = new SQLite3($dbPath, SQLITE3_OPEN_READONLY);
    $db->busyTimeout(3000);
    $readings = [];
    $result = $db->query('SELECT timestamp, ambient_temperature, humidity, kiln_temperature, source FROM readings ORDER BY timestamp DESC LIMIT 120');
    while ($row = $result->fetchArray(SQLITE3_ASSOC)) {
        $readings[] = $row;
    }
    $readings = array_reverse($readings);

    $minutes = [];
    $result = $db->query("SELECT substr(timestamp, 1, 16) || ':00+00:00' AS timestamp,
        AVG(ambient_temperature) AS ambient_temperature,
        AVG(humidity) AS humidity,
        AVG(kiln_temperature) AS kiln_temperature,
        'minute' AS source
        FROM readings
        GROUP BY substr(timestamp, 1, 16)
        ORDER BY timestamp DESC
        LIMIT 180");
    while ($row = $result->fetchArray(SQLITE3_ASSOC)) {
        $minutes[] = $row;
    }
    $minutes = array_reverse($minutes);
    $db->close();

    return [
        'readings' => $readings,
        'minutes' => $minutes,
        'latest' => $readings === [] ? null : $readings[count($readings) - 1],
    ];
};

header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store, no-cache, must-revalidate, max-age=0');
try {
    echo json_encode($queryReadings(), JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES | JSON_THROW_ON_ERROR);
} catch (Throwable $error) {
    error_log('Kiln dashboard query error: ' . $error->getMessage());
    http_response_code(500);
    echo json_encode(['error' => 'Database read failed'], JSON_UNESCAPED_UNICODE);
}
