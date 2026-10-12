<?php
declare(strict_types=1);

$dbPath = getenv('KILN_SQLITE_PATH') ?: (__DIR__ . '/data/readings.sqlite3');
$latest = null;
$readings = [];
$error = null;
if (is_file($dbPath)) {
    try {
        $db = new SQLite3($dbPath, SQLITE3_OPEN_READONLY);
        $db->busyTimeout(3000);
        $result = $db->query('SELECT timestamp, ambient_temperature, humidity, kiln_temperature, source FROM readings ORDER BY timestamp DESC LIMIT 100');
        while ($row = $result->fetchArray(SQLITE3_ASSOC)) {
            $readings[] = $row;
        }
        $latest = $readings[0] ?? null;
    } catch (Throwable $exception) {
        $error = 'Не вдалося прочитати базу даних.';
        error_log('Kiln dashboard error: ' . $exception->getMessage());
    }
}
$format = static fn($value, string $unit): string => $value === null ? '—' : number_format((float)$value, 1, ',', ' ') . $unit;
$escape = static fn($value): string => htmlspecialchars((string)$value, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
?><!doctype html>
<html lang="uk">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta http-equiv="refresh" content="10">
  <title>Монітор печі</title>
  <style>
    :root{color-scheme:dark;font-family:system-ui,sans-serif;background:#111714;color:#edf3ef}body{max-width:1100px;margin:0 auto;padding:28px 18px}h1{margin:0 0 8px}.muted{color:#a7b2ac}.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;margin:24px 0}.card,section{background:#1b2420;border:1px solid #2d3933;border-radius:12px;padding:18px}.label{color:#a7b2ac;font-size:.9rem}.value{font-size:2rem;font-weight:700;margin-top:8px}table{width:100%;border-collapse:collapse}th,td{text-align:left;padding:11px 10px;border-bottom:1px solid #2d3933;white-space:nowrap}th{color:#a7b2ac}section{overflow-x:auto}.notice{padding:14px;background:#382d1c;border-radius:8px;margin:18px 0}
  </style>
</head>
<body>
  <h1>Монітор печі</h1>
  <div class="muted">Сторінка оновлюється кожні 10 секунд. Час показано за часовим поясом браузера.</div>
  <?php if ($error !== null): ?><p class="notice"><?= $escape($error) ?></p>
  <?php elseif ($latest === null): ?><p class="notice">Даних поки немає. Перевірте адресу приймача та налаштування відправника.</p>
  <?php else: ?>
    <div class="cards">
      <div class="card"><div class="label">Температура повітря</div><div class="value"><?= $format($latest['ambient_temperature'], ' °C') ?></div></div>
      <div class="card"><div class="label">Вологість</div><div class="value"><?= $format($latest['humidity'], ' %') ?></div></div>
      <div class="card"><div class="label">Температура печі</div><div class="value"><?= $format($latest['kiln_temperature'], ' °C') ?></div></div>
    </div>
    <p class="muted">Останнє вимірювання: <?= $escape($latest['timestamp']) ?> · <?= $escape($latest['source']) ?></p>
  <?php endif; ?>
  <section>
    <h2>Останні вимірювання</h2>
    <table><thead><tr><th>Час (UTC)</th><th>Повітря</th><th>Вологість</th><th>Піч</th><th>Джерело</th></tr></thead><tbody>
    <?php foreach ($readings as $reading): ?><tr>
      <td><?= $escape($reading['timestamp']) ?></td>
      <td><?= $format($reading['ambient_temperature'], ' °C') ?></td>
      <td><?= $format($reading['humidity'], ' %') ?></td>
      <td><?= $format($reading['kiln_temperature'], ' °C') ?></td>
      <td><?= $escape($reading['source']) ?></td>
    </tr><?php endforeach; ?>
    </tbody></table>
  </section>
</body>
</html>
