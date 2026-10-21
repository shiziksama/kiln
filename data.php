<?php
declare(strict_types=1);

$dbPath = getenv('KILN_SQLITE_PATH') ?: (__DIR__ . '/data/readings.sqlite3');
$queryReadings = static function () use ($dbPath): array {
    // Include the current minute and the preceding 1439 minutes in UTC.
    $end = intdiv(time(), 60) * 60;
    $start = $end - 1439 * 60;
    $minuteSlots = [];
    for ($time = $start; $time <= $end; $time += 60) {
        $timestamp = gmdate('Y-m-d\TH:i:00\Z', $time);
        $minuteSlots[$timestamp] = [
            'timestamp' => $timestamp, 'ambient_temperature' => null,
            'humidity' => null, 'kiln_temperature' => null, 'source' => 'minute',
        ];
    }
    if (!is_file($dbPath)) {
        return ['readings' => [], 'minutes' => array_values($minuteSlots), 'latest' => null];
    }

    $db = new SQLite3($dbPath, SQLITE3_OPEN_READONLY);
    $db->busyTimeout(3000);
    $readings = [];
    $result = $db->query('SELECT timestamp, ambient_temperature, humidity, kiln_temperature, source FROM readings ORDER BY timestamp DESC LIMIT 120');
    while ($row = $result->fetchArray(SQLITE3_ASSOC)) {
        $readings[] = $row;
    }
    $readings = array_reverse($readings);

    $statement = $db->prepare("SELECT strftime('%Y-%m-%dT%H:%M:00Z', timestamp) AS timestamp,
        AVG(ambient_temperature) AS ambient_temperature,
        AVG(humidity) AS humidity,
        AVG(kiln_temperature) AS kiln_temperature,
        'minute' AS source
        FROM readings
        WHERE julianday(timestamp) >= julianday(:start)
          AND julianday(timestamp) < julianday(:end)
        GROUP BY strftime('%Y-%m-%dT%H:%M:00Z', timestamp)");
    $statement->bindValue(':start', gmdate('Y-m-d\TH:i:s\Z', $start), SQLITE3_TEXT);
    $statement->bindValue(':end', gmdate('Y-m-d\TH:i:s\Z', $end + 60), SQLITE3_TEXT);
    $result = $statement->execute();
    while ($row = $result->fetchArray(SQLITE3_ASSOC)) {
        $minuteSlots[$row['timestamp']] = $row;
    }
    $minutes = array_values($minuteSlots);
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
