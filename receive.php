<?php
declare(strict_types=1);

header('Content-Type: application/json; charset=utf-8');

function respond(int $status, array $body): never
{
    http_response_code($status);
    echo json_encode($body, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
    exit;
}

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    header('Allow: POST');
    respond(405, ['error' => 'Use POST']);
}

$expectedToken = getenv('KILN_API_TOKEN') ?: '';
$authorization = $_SERVER['HTTP_AUTHORIZATION'] ?? '';
if ($expectedToken === '') {
    respond(503, ['error' => 'Receiver token is not configured']);
}
if (!hash_equals('Bearer ' . $expectedToken, $authorization)) {
    respond(401, ['error' => 'Unauthorized']);
}

$contentType = strtolower(trim(explode(';', $_SERVER['CONTENT_TYPE'] ?? '')[0]));
if ($contentType !== 'application/json') {
    respond(415, ['error' => 'Content-Type must be application/json']);
}
$payload = json_decode(file_get_contents('php://input') ?: '', true);
if (!is_array($payload)) {
    respond(400, ['error' => 'Invalid JSON']);
}

$timestamp = $payload['timestamp'] ?? gmdate('Y-m-d\TH:i:s\Z');
if (!is_string($timestamp) || strtotime($timestamp) === false || strlen($timestamp) > 40) {
    respond(422, ['error' => 'Invalid timestamp']);
}
$source = $payload['source'] ?? 'remote';
if (!is_string($source) || strlen($source) > 80) {
    respond(422, ['error' => 'Invalid source']);
}
$values = [];
foreach (['ambient_temperature', 'humidity', 'kiln_temperature'] as $field) {
    $value = $payload[$field] ?? null;
    if ($value !== null && (!is_numeric($value) || !is_finite((float)$value))) {
        respond(422, ['error' => 'Invalid value for ' . $field]);
    }
    $values[$field] = $value === null ? null : (float)$value;
}

$dbPath = getenv('KILN_SQLITE_PATH') ?: (__DIR__ . '/data/readings.sqlite3');
$dbDir = dirname($dbPath);
if (!is_dir($dbDir) && !mkdir($dbDir, 0775, true) && !is_dir($dbDir)) {
    respond(500, ['error' => 'Cannot create database directory']);
}
try {
    $db = new SQLite3($dbPath, SQLITE3_OPEN_READWRITE | SQLITE3_OPEN_CREATE);
    $db->busyTimeout(5000);
    $db->exec('PRAGMA journal_mode=WAL');
    $db->exec('CREATE TABLE IF NOT EXISTS readings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL UNIQUE,
        ambient_temperature REAL,
        humidity REAL,
        kiln_temperature REAL,
        source TEXT NOT NULL
    )');
    $statement = $db->prepare('INSERT OR IGNORE INTO readings
        (timestamp, ambient_temperature, humidity, kiln_temperature, source)
        VALUES (:timestamp, :ambient_temperature, :humidity, :kiln_temperature, :source)');
    $statement->bindValue(':timestamp', $timestamp, SQLITE3_TEXT);
    foreach (['ambient_temperature', 'humidity', 'kiln_temperature'] as $field) {
        $statement->bindValue(':' . $field, $values[$field], $values[$field] === null ? SQLITE3_NULL : SQLITE3_FLOAT);
    }
    $statement->bindValue(':source', $source, SQLITE3_TEXT);
    $statement->execute();
    respond(200, ['ok' => true]);
} catch (Throwable $error) {
    error_log('Kiln receiver error: ' . $error->getMessage());
    respond(500, ['error' => 'Database write failed']);
}
