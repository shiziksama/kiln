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

if (($_GET['data'] ?? '') === '1') {
    header('Content-Type: application/json; charset=utf-8');
    header('Cache-Control: no-store, no-cache, must-revalidate, max-age=0');
    try {
        echo json_encode($queryReadings(), JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES | JSON_THROW_ON_ERROR);
    } catch (Throwable $error) {
        error_log('Kiln dashboard query error: ' . $error->getMessage());
        http_response_code(500);
        echo json_encode(['error' => 'Database read failed'], JSON_UNESCAPED_UNICODE);
    }
    exit;
}
?><!doctype html>
<html lang="uk">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="theme-color" content="#101312">
  <title>Kiln Monitor</title>
  <style>
    :root{color-scheme:dark;font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:#101312;color:#f4f1ea}*{box-sizing:border-box}body{margin:0;min-width:320px;background:linear-gradient(180deg,rgba(25,31,29,.96),#101312),#101312}.shell{width:min(1180px,calc(100% - 32px));margin:0 auto;padding:28px 0}.topbar{display:flex;align-items:center;justify-content:space-between;gap:16px;margin-bottom:20px}h1,h2,p{margin:0}h1{font-size:28px;font-weight:760}.topbar p{margin-top:6px;color:#aeb7b1;font-size:14px}.source{min-width:84px;height:36px;display:grid;place-items:center;border:1px solid #3d4944;border-radius:8px;color:#d3d9d5;font-size:13px;text-transform:uppercase}.metrics{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin-bottom:12px}.metrics article,.chart-panel,.latest-panel{border:1px solid #2f3935;border-radius:8px;background:#171d1b}.metrics article{min-height:100px;padding:18px;display:flex;flex-direction:column;justify-content:space-between}.metrics span,.panel-title span,.latest-panel .label{color:#9fa9a4;font-size:13px}.metrics strong{font-size:clamp(30px,5vw,48px);line-height:1}.dashboard{display:grid;grid-template-columns:minmax(0,2fr) minmax(250px,1fr);gap:12px}.chart-panel,.latest-panel{padding:16px;min-width:0}.panel-title{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:12px}.panel-title h2{font-size:15px;font-weight:680}.combined-chart{min-height:430px}.minute-chart{grid-column:1/-1}.legend{display:flex;align-items:center;justify-content:flex-end;flex-wrap:wrap;gap:8px;color:#b7c0bb;font-size:12px}.legend button{height:30px;padding:0 10px;display:inline-flex;align-items:center;gap:6px;border:1px solid #3d4944;border-radius:8px;background:#1d2421;color:#d6ded9;cursor:pointer;font:inherit;white-space:nowrap}.legend button:not(.active){color:#76817b;background:#141917}.legend button:not(.active) i{opacity:.25}.legend button:focus-visible{outline:2px solid #d6ded9;outline-offset:2px}.legend button:hover{border-color:#596760}.legend i{width:10px;height:10px;display:inline-block;border-radius:999px}.ambient{background:#f2b84b}.humidity{background:#61c3ff}.kiln{background:#ff5a63}canvas{width:100%;height:360px;display:block}.minute-chart canvas{height:320px}.latest-panel .label{margin-bottom:6px}.latest-panel .stamp{font-size:18px;margin-bottom:18px;overflow-wrap:anywhere}.latest-panel .small{color:#aeb7b1;font-size:13px;line-height:1.6}.latest-panel .state{margin-top:18px;padding:10px;border-radius:6px;background:#202925;color:#cbd4ce;font-size:13px}.latest-panel .state.error{background:#382d1c;color:#f2ca84}@media(max-width:820px){.shell{width:min(100% - 20px,1180px);padding:18px 0}.topbar{align-items:flex-start;flex-direction:column}.metrics,.dashboard{grid-template-columns:1fr}.panel-title{align-items:flex-start;flex-direction:column}.minute-chart{grid-column:auto}}
  </style>
</head>
<body>
  <main class="shell">
    <header class="topbar">
      <div><h1>Kiln Monitor</h1><p id="status">Завантаження даних…</p></div>
      <div class="source" id="source">—</div>
    </header>
    <section class="metrics" aria-label="Поточні значення">
      <article><span>Температура</span><strong id="ambient-temperature">--</strong></article>
      <article><span>Вологість</span><strong id="humidity">--</strong></article>
      <article><span>Пічка</span><strong id="kiln-temperature">--</strong></article>
    </section>
    <section class="dashboard">
      <div class="chart-panel combined-chart">
        <div class="panel-title">
          <h2>Графік показників</h2>
          <div class="legend" aria-label="Легенда графіка">
            <button type="button" class="active" data-series="ambient_temperature" aria-pressed="true"><i class="ambient"></i>Температура</button>
            <button type="button" class="active" data-series="humidity" aria-pressed="true"><i class="humidity"></i>Вологість</button>
            <button type="button" class="active" data-series="kiln_temperature" aria-pressed="true"><i class="kiln"></i>Пічка</button>
          </div>
        </div>
        <canvas id="readings-chart" height="360"></canvas>
      </div>
      <aside class="latest-panel">
        <div class="panel-title"><h2>Останній вимір</h2></div>
        <div class="label">Час у вашому часовому поясі</div>
        <div class="stamp" id="last-seen">—</div>
        <div class="small">Температуру печі беремо з камери, якщо вона доступна. Без камери графік показує інші показники.</div>
        <div class="state" id="connection-state">Очікування даних</div>
      </aside>
      <div class="chart-panel minute-chart">
        <div class="panel-title"><h2>По хвилинах</h2><span>Середні значення</span></div>
        <canvas id="minute-chart" height="320"></canvas>
      </div>
    </section>
  </main>
  <script>
    const series = [
      {field:"ambient_temperature",label:"Температура",unit:"°C",color:"#f2b84b",minSpan:10,hardMin:-20,hardMax:80,axis:"left"},
      {field:"humidity",label:"Вологість",unit:"%",color:"#61c3ff",minSpan:20,hardMin:0,hardMax:100,axis:"right-inner"},
      {field:"kiln_temperature",label:"Пічка",unit:"°C",color:"#ff5a63",minSpan:50,hardMin:0,hardMax:1300,axis:"right"},
    ];
    let visibleSeries;
    try {
      const saved = JSON.parse(localStorage.getItem("kiln-visible-series") || "null");
      visibleSeries = new Set(Array.isArray(saved) ? saved : series.map(item => item.field));
    } catch (_) { visibleSeries = new Set(series.map(item => item.field)); }

    function formatValue(value, unit) {
      return value === null || value === undefined || Number.isNaN(Number(value)) ? "--" : `${Number(value).toFixed(1)}${unit}`;
    }
    function formatTime(timestamp, minutesOnly = false) {
      if (!timestamp) return "—";
      const date = new Date(timestamp);
      if (Number.isNaN(date.getTime())) return timestamp;
      return date.toLocaleTimeString("uk-UA", {hour:"2-digit",minute:"2-digit",...(minutesOnly ? {} : {second:"2-digit"})});
    }
    function setLatest(reading) {
      document.getElementById("ambient-temperature").textContent = formatValue(reading?.ambient_temperature, "°");
      document.getElementById("humidity").textContent = formatValue(reading?.humidity, "%");
      document.getElementById("kiln-temperature").textContent = formatValue(reading?.kiln_temperature, "°");
      document.getElementById("source").textContent = reading?.source || "—";
      document.getElementById("last-seen").textContent = reading ? `${formatTime(reading.timestamp)} · ${formatDate(reading.timestamp)}` : "—";
      document.getElementById("status").textContent = reading ? `Останнє оновлення ${formatTime(reading.timestamp)}` : "Дані ще не надійшли";
      document.getElementById("connection-state").textContent = reading ? "Дані оновлюються кожні 10 секунд" : "Очікування першого виміру";
      document.getElementById("connection-state").classList.remove("error");
    }
    function formatDate(timestamp) {
      const date = new Date(timestamp);
      return Number.isNaN(date.getTime()) ? "" : date.toLocaleDateString("uk-UA", {day:"2-digit",month:"short"});
    }
    function getRange(readings, config) {
      const values = readings.map(r => r[config.field]).filter(v => v !== null && v !== undefined && Number.isFinite(Number(v))).map(Number);
      if (!values.length) return {min:config.hardMin,max:Math.min(config.hardMax,config.hardMin+config.minSpan)};
      let min = Math.min(...values), max = Math.max(...values);
      const span = Math.max(max-min,config.minSpan), center = (min+max)/2;
      min = Math.max(config.hardMin,center-span/2-span*.12);
      max = Math.min(config.hardMax,center+span/2+span*.12);
      if (max-min < config.minSpan) max = Math.min(config.hardMax,min+config.minSpan);
      return {min,max};
    }
    function drawChart(canvas, readings, minutesOnly = false) {
      const ctx = canvas.getContext("2d"), ratio = window.devicePixelRatio || 1;
      const width = canvas.clientWidth, height = canvas.clientHeight;
      canvas.width = Math.floor(width*ratio); canvas.height = Math.floor(height*ratio); ctx.scale(ratio,ratio); ctx.clearRect(0,0,width,height);
      const pad = {top:20,right:98,bottom:46,left:58}, plotW = width-pad.left-pad.right, plotH = height-pad.top-pad.bottom;
      const active = series.filter(item => visibleSeries.has(item.field));
      const ranges = Object.fromEntries(active.map(item => [item.field,getRange(readings,item)]));
      ctx.strokeStyle="#29332f";ctx.lineWidth=1;
      for(let i=0;i<=4;i++){const y=pad.top+plotH*i/4;ctx.beginPath();ctx.moveTo(pad.left,y);ctx.lineTo(width-pad.right,y);ctx.stroke();}
      const tickCount=Math.min(5,readings.length);
      ctx.strokeStyle="#33403b";ctx.fillStyle="#9fa9a4";ctx.font="12px system-ui";ctx.textAlign="center";ctx.textBaseline="top";
      for(let tick=0;tick<tickCount;tick++){const idx=tickCount===1?0:Math.round(tick/(tickCount-1)*(readings.length-1));const x=pad.left+(readings.length<=1?plotW:idx/(readings.length-1)*plotW);ctx.beginPath();ctx.moveTo(x,pad.top);ctx.lineTo(x,pad.top+plotH+5);ctx.stroke();ctx.fillText(formatTime(readings[idx]?.timestamp,minutesOnly),x,pad.top+plotH+10);}
      ctx.textAlign="left";ctx.textBaseline="alphabetic";
      active.forEach(item=>{const range=ranges[item.field], axisX=item.axis==="left"?pad.left-8:item.axis==="right-inner"?width-pad.right+8:width-44;ctx.fillStyle=item.color;ctx.font="12px system-ui";ctx.textAlign=item.axis==="left"?"right":"left";ctx.fillText(`${Math.round(range.max)}${item.unit==="%"?"%":"°"}`,axisX,pad.top+4);ctx.fillText(`${Math.round(range.min)}${item.unit==="%"?"%":"°"}`,axisX,pad.top+plotH);});
      ctx.textAlign="left";
      if(!active.length||!active.some(item=>readings.some(r=>r[item.field]!==null&&r[item.field]!==undefined))){ctx.fillStyle="#7e8984";ctx.font="14px system-ui";ctx.fillText(active.length?"Немає даних":"Всі лінії вимкнені",pad.left,pad.top+28);return;}
      active.forEach(item=>{const points=[];readings.forEach((r,index)=>{const value=r[item.field];if(value===null||value===undefined||!Number.isFinite(Number(value)))return;points.push({x:pad.left+(readings.length<=1?plotW:index/(readings.length-1)*plotW),y:pad.top+plotH-(Number(value)-ranges[item.field].min)/(ranges[item.field].max-ranges[item.field].min)*plotH});});if(!points.length)return;ctx.strokeStyle=item.color;ctx.lineWidth=2;ctx.beginPath();points.forEach((p,i)=>i?ctx.lineTo(p.x,p.y):ctx.moveTo(p.x,p.y));ctx.stroke();const last=points[points.length-1];ctx.fillStyle=item.color;ctx.beginPath();ctx.arc(last.x,last.y,4,0,Math.PI*2);ctx.fill();});
    }
    async function refresh() {
      if(document.hidden)return;
      try {
        const response=await fetch("?data=1",{cache:"no-store"});
        if(!response.ok)throw new Error("request failed");
        const data=await response.json();
        const readings=data.readings||[],minutes=data.minutes||[];
        setLatest(data.latest);
        drawChart(document.getElementById("readings-chart"),readings.slice(-120));
        drawChart(document.getElementById("minute-chart"),minutes.slice(-180),true);
      } catch (_) {
        document.getElementById("status").textContent="Не вдалося отримати дані";
        document.getElementById("connection-state").textContent="Помилка читання бази даних";
        document.getElementById("connection-state").classList.add("error");
      }
    }
    document.querySelectorAll("[data-series]").forEach(button=>{
      const field=button.dataset.series;
      button.classList.toggle("active",visibleSeries.has(field));
      button.setAttribute("aria-pressed",visibleSeries.has(field)?"true":"false");
      button.addEventListener("click",()=>{if(visibleSeries.has(field))visibleSeries.delete(field);else visibleSeries.add(field);try{localStorage.setItem("kiln-visible-series",JSON.stringify([...visibleSeries]));}catch(_){}button.classList.toggle("active",visibleSeries.has(field));button.setAttribute("aria-pressed",visibleSeries.has(field)?"true":"false");refresh();});
    });
    refresh();
    setInterval(refresh,10000);
    window.addEventListener("resize",refresh);
    document.addEventListener("visibilitychange",()=>{if(!document.hidden)refresh();});
  </script>
</body>
</html>
