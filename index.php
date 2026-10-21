<!doctype html>
<html lang="uk">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="theme-color" content="#101312">
  <title>Kiln Monitor</title>
  <style>
    :root{color-scheme:dark;font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:#101312;color:#f4f1ea}*{box-sizing:border-box}body{margin:0;min-width:320px;background:linear-gradient(180deg,rgba(25,31,29,.96),#101312),#101312}.shell{width:min(1180px,calc(100% - 32px));margin:0 auto;padding:28px 0}.topbar{display:flex;align-items:center;justify-content:space-between;gap:16px;margin-bottom:20px}h1,h2,p{margin:0}h1{font-size:28px;font-weight:760}.topbar p{margin-top:6px;color:#aeb7b1;font-size:14px}.source{min-width:84px;height:36px;display:grid;place-items:center;border:1px solid #3d4944;border-radius:8px;color:#d3d9d5;font-size:13px;text-transform:uppercase}.metrics{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin-bottom:12px}.metrics article,.chart-panel,.latest-panel{border:1px solid #2f3935;border-radius:8px;background:#171d1b}.metrics article{min-height:100px;padding:18px;display:flex;flex-direction:column;justify-content:space-between}.metrics span,.panel-title span,.latest-panel .label{color:#9fa9a4;font-size:13px}.metrics strong{font-size:clamp(30px,5vw,48px);line-height:1}.dashboard{display:grid;grid-template-columns:minmax(0,2fr) minmax(250px,1fr);gap:12px}.chart-panel,.latest-panel{padding:16px;min-width:0}.panel-title{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:12px}.panel-title h2{font-size:15px;font-weight:680}.combined-chart{min-height:430px}.minute-chart{grid-column:1/-1}.legend{display:flex;align-items:center;justify-content:flex-end;flex-wrap:wrap;gap:8px;color:#b7c0bb;font-size:12px}.legend button{height:30px;padding:0 10px;display:inline-flex;align-items:center;gap:6px;border:1px solid #3d4944;border-radius:8px;background:#1d2421;color:#d6ded9;cursor:pointer;font:inherit;white-space:nowrap}.legend button:not(.active){color:#76817b;background:#141917}.legend button:not(.active) i{opacity:.25}.legend button:focus-visible{outline:2px solid #d6ded9;outline-offset:2px}.legend button:hover{border-color:#596760}.legend i{width:10px;height:10px;display:inline-block;border-radius:999px}.ambient{background:#f2b84b}.humidity{background:#61c3ff}.kiln{background:#ff5a63}canvas{width:100%;height:360px;display:block}.minute-chart canvas{height:320px}.latest-panel .label{margin-bottom:6px}.latest-panel .stamp{font-size:18px;margin-bottom:18px;overflow-wrap:anywhere}.latest-panel .small{color:#aeb7b1;font-size:13px;line-height:1.6}.latest-panel .state{margin-top:18px;padding:10px;border-radius:6px;background:#202925;color:#cbd4ce;font-size:13px}.latest-panel .state.error{background:#382d1c;color:#f2ca84}@media(max-width:820px){.shell{width:min(100% - 20px,1180px);padding:18px 0}.topbar{align-items:flex-start;flex-direction:column}.metrics,.dashboard{grid-template-columns:1fr}.panel-title{align-items:flex-start;flex-direction:column}.minute-chart{grid-column:auto}}
    .chart-panel{position:relative}.chart-tooltip{position:absolute;z-index:2;pointer-events:none;white-space:pre-line;background:#101312;border:1px solid #596760;border-radius:6px;padding:10px;font-size:13px;line-height:1.6;max-width:calc(100% - 20px)}.chart-cursor{position:absolute;width:1px;background:#aeb7b1;pointer-events:none}
    .zoom-controls{display:flex;align-items:center;flex-wrap:wrap;gap:8px}.zoom-controls button{background:#202925;color:#f4f1ea;border:1px solid #596760;border-radius:6px;padding:6px 12px;cursor:pointer}.zoom-controls button:disabled{opacity:.4;cursor:default}.zoom-controls span,.zoom-help{color:#aeb7b1;font-size:12px}.zoom-help{margin:8px 0}#minute-chart{touch-action:pan-y;cursor:grab}#minute-chart.dragging{cursor:grabbing}
    .power-warning{margin-bottom:16px;padding:14px 16px;border:1px solid #d94b55;border-radius:8px;background:#451d24;color:#ffb4bb}
  </style>
</head>
<body>
  <main class="shell">
    <header class="topbar">
      <div><h1>Kiln Monitor</h1><p>Від останнього виміру: <span id="reading-age">—</span><br>Графіки оновлені: <span id="fetch-age">—</span></p></div>
      <div class="source" id="source">—</div>
    </header>
    <div id="power-warning" class="power-warning" role="status" hidden>У майстерні немає світла</div>
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
        <div class="panel-title"><h2>По хвилинах</h2><span>Останні 24 години · середні значення</span></div>
        <div class="zoom-controls">
          <button type="button" id="zoom-in" aria-label="Наблизити графік">＋</button>
          <button type="button" id="zoom-out" aria-label="Віддалити графік">−</button>
          <button type="button" id="zoom-reset">Усі 24 години</button>
          <span id="zoom-range"></span>
        </div>
        <p class="zoom-help">Коліщатко — масштаб, перетягування — переміщення</p>
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
    let latestTimestamp = null, lastFetchAt = null, fetching = false;
    const chartStates = new Map();
    let minuteView = null;
    function minuteWindow(readings) {
      const count = Math.min(readings.length, minuteView?.count ?? readings.length);
      const requested = minuteView ? Math.round((minuteView.start - Date.parse(readings[0]?.timestamp)) / 60000) : 0;
      const start = Math.max(0, Math.min(readings.length-count, requested));
      if (minuteView && readings.length) minuteView = {start:Date.parse(readings[start].timestamp),count};
      return readings.slice(start, start+count);
    }
    function zoomMinutes(factor, anchor = .5) {
      const state = chartStates.get(document.getElementById("minute-chart"));
      if (!state || !state.readings.length) return;
      const count = Math.max(Math.min(10,state.allReadings.length), Math.min(state.allReadings.length, Math.round(state.readings.length*factor)));
      const start = Date.parse(state.readings[0].timestamp) + Math.round((state.readings.length-count)*anchor)*60000;
      minuteView = count === state.allReadings.length ? null : {start,count};
      redraw();
    }
    function elapsed(timestamp) {
      if (timestamp === null || !Number.isFinite(timestamp)) return "—";
      const seconds = Math.max(0, Math.floor((Date.now() - timestamp) / 1000));
      return `${Math.floor(seconds / 3600)} год ${String(Math.floor(seconds / 60) % 60).padStart(2,"0")} хв ${String(seconds % 60).padStart(2,"0")} с`;
    }
    function plural(value, forms) {
      const lastTwo = value % 100, last = value % 10;
      return forms[lastTwo >= 11 && lastTwo <= 14 ? 2 : last === 1 ? 0 : last >= 2 && last <= 4 ? 1 : 2];
    }
    function updateTimers() {
      const warning = document.getElementById("power-warning");
      const age = Number.isFinite(latestTimestamp) ? Date.now() - latestTimestamp : 0;
      warning.hidden = age <= 5 * 60 * 1000;
      if (!warning.hidden) {
        const totalMinutes = Math.floor(age / 60000);
        const hours = Math.floor(totalMinutes / 60), minutes = totalMinutes % 60;
        const duration = [
          ...(hours ? [`${hours} ${plural(hours, ["годину", "години", "годин"])}`] : []),
          `${minutes} ${plural(minutes, ["хвилину", "хвилини", "хвилин"])}`,
        ].join(" ");
        warning.textContent = `У майстерні немає світла ${duration}`;
      }
      document.getElementById("reading-age").textContent = elapsed(latestTimestamp);
      document.getElementById("fetch-age").textContent = lastFetchAt === null ? "—" : `${Math.max(0, Math.floor((Date.now() - lastFetchAt) / 1000))} с тому`;
    }
    function setLatest(reading) {
      document.getElementById("ambient-temperature").textContent = formatValue(reading?.ambient_temperature, "°");
      document.getElementById("humidity").textContent = formatValue(reading?.humidity, "%");
      document.getElementById("kiln-temperature").textContent = formatValue(reading?.kiln_temperature, "°");
      document.getElementById("source").textContent = reading?.source || "—";
      document.getElementById("last-seen").textContent = reading ? `${formatTime(reading.timestamp)} · ${formatDate(reading.timestamp)}` : "—";
      latestTimestamp = reading ? Date.parse(reading.timestamp) : null;
      updateTimers();
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
      const allReadings = readings;
      if (minutesOnly) {
        readings = minuteWindow(allReadings);
        document.getElementById("zoom-in").disabled = readings.length <= 10;
        document.getElementById("zoom-out").disabled = readings.length === allReadings.length;
        document.getElementById("zoom-range").textContent = readings.length ?
          `${formatDate(readings[0].timestamp)} ${formatTime(readings[0].timestamp,true)} — ${formatDate(readings.at(-1).timestamp)} ${formatTime(readings.at(-1).timestamp,true)}` : "";
      }
      const ctx = canvas.getContext("2d"), ratio = window.devicePixelRatio || 1;
      const width = canvas.clientWidth, height = canvas.clientHeight;
      canvas.width = Math.floor(width*ratio); canvas.height = Math.floor(height*ratio); ctx.scale(ratio,ratio); ctx.clearRect(0,0,width,height);
      const pad = {top:20,right:98,bottom:46,left:58}, plotW = width-pad.left-pad.right, plotH = height-pad.top-pad.bottom;
      chartStates.set(canvas, {readings, allReadings, minutesOnly, pad, plotW, plotH});
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
      active.forEach(item => {
        const range = ranges[item.field];
        let connected = false;
        ctx.strokeStyle = item.color; ctx.fillStyle = item.color; ctx.lineWidth = 2;
        ctx.beginPath();
        const points = [];
        readings.forEach((reading, index) => {
          const value = reading[item.field];
          if (value === null || value === undefined || !Number.isFinite(Number(value))) {
            connected = false;
            return;
          }
          const x = pad.left + (readings.length <= 1 ? plotW : index / (readings.length - 1) * plotW);
          const y = pad.top + plotH - (Number(value) - range.min) / (range.max - range.min) * plotH;
          if (connected) ctx.lineTo(x,y); else ctx.moveTo(x,y);
          connected = true;
          points.push({x,y});
        });
        ctx.stroke();
        // Dots also keep isolated measurements visible between gaps.
        points.forEach(({x,y}) => {ctx.beginPath();ctx.arc(x,y,2,0,Math.PI*2);ctx.fill();});
      });
    }
    document.querySelectorAll("canvas").forEach(canvas => {
      const tooltip = document.createElement("div"), cursor = document.createElement("div");
      tooltip.className = "chart-tooltip"; cursor.className = "chart-cursor";
      tooltip.hidden = cursor.hidden = true;
      canvas.parentElement.append(cursor, tooltip);
      function hide() { tooltip.hidden = cursor.hidden = true; }
      canvas.addEventListener("pointerleave", hide);
      canvas.addEventListener("pointercancel", hide);
      canvas.addEventListener("pointermove", event => {
        const state = chartStates.get(canvas);
        if (!state || !state.readings.length) return hide();
        const rect = canvas.getBoundingClientRect();
        const x = event.clientX - rect.left, y = event.clientY - rect.top;
        if (x < state.pad.left || x > state.pad.left + state.plotW || y < state.pad.top || y > state.pad.top + state.plotH) return hide();
        const index = Math.round((x-state.pad.left)/state.plotW*(state.readings.length-1));
        const reading = state.readings[index];
        tooltip.textContent = `${formatDate(reading.timestamp)} · ${formatTime(reading.timestamp, state.minutesOnly)}\n` +
          series.filter(item => visibleSeries.has(item.field)).map(item => `${item.label}: ${formatValue(reading[item.field],item.unit)}`).join("\n");
        tooltip.hidden = cursor.hidden = false;
        tooltip.style.left = `${Math.max(10,Math.min(canvas.offsetLeft+x+12,canvas.parentElement.clientWidth-tooltip.offsetWidth-10))}px`;
        tooltip.style.top = `${canvas.offsetTop+state.pad.top+8}px`;
        cursor.style.left = `${canvas.offsetLeft+state.pad.left+(state.readings.length<=1?state.plotW:index/(state.readings.length-1)*state.plotW)}px`;
        cursor.style.top = `${canvas.offsetTop+state.pad.top}px`;
        cursor.style.height = `${state.plotH}px`;
      });
    });
    function redraw() {
      chartStates.forEach((state, canvas) => drawChart(canvas, state.allReadings, state.minutesOnly));
      document.querySelectorAll(".chart-tooltip,.chart-cursor").forEach(element => {element.hidden = true;});
    }

    const minuteCanvas = document.getElementById("minute-chart");
    document.getElementById("zoom-in").addEventListener("click", () => zoomMinutes(.5));
    document.getElementById("zoom-out").addEventListener("click", () => zoomMinutes(2));
    document.getElementById("zoom-reset").addEventListener("click", () => {minuteView=null;redraw();});
    minuteCanvas.addEventListener("wheel", event => {
      const state = chartStates.get(minuteCanvas);
      if (!state) return;
      const x = event.clientX-minuteCanvas.getBoundingClientRect().left;
      if (x < state.pad.left || x > state.pad.left+state.plotW) return;
      event.preventDefault();
      zoomMinutes(event.deltaY < 0 ? .8 : 1.25, (x-state.pad.left)/state.plotW);
    }, {passive:false});
    let drag = null;
    minuteCanvas.addEventListener("pointerdown", event => {
      const state = chartStates.get(minuteCanvas);
      if (!state || !minuteView || event.button !== 0 || drag) return;
      const rect = minuteCanvas.getBoundingClientRect();
      const x = event.clientX-rect.left, y=event.clientY-rect.top;
      if (x<state.pad.left || x>state.pad.left+state.plotW || y<state.pad.top || y>state.pad.top+state.plotH) return;
      drag = {id:event.pointerId,x:event.clientX,start:Date.parse(state.readings[0].timestamp),count:state.readings.length,plotW:state.plotW};
      minuteCanvas.setPointerCapture(event.pointerId);
      minuteCanvas.classList.add("dragging");
    });
    minuteCanvas.addEventListener("pointermove", event => {
      if (!drag || event.pointerId!==drag.id) return;
      minuteView = {start:drag.start-Math.round((event.clientX-drag.x)/drag.plotW*(drag.count-1))*60000,count:drag.count};
      redraw();
    });
    function endDrag(event) {
      if (!drag || event.pointerId!==drag.id) return;
      drag=null;
      minuteCanvas.classList.remove("dragging");
      if (minuteCanvas.hasPointerCapture(event.pointerId)) minuteCanvas.releasePointerCapture(event.pointerId);
    }
    ["pointerup","pointercancel","lostpointercapture"].forEach(name=>minuteCanvas.addEventListener(name,endDrag));

    async function refresh() {
      if(document.hidden || fetching)return;
      fetching = true;
      try {
        const response=await fetch("data.php",{cache:"no-store"});
        if(!response.ok)throw new Error("request failed");
        const data=await response.json();
        if (!Array.isArray(data.readings) || !Array.isArray(data.minutes)) throw new Error("Invalid data");
        lastFetchAt = Date.now();
        const readings=data.readings||[],minutes=data.minutes||[];
        setLatest(data.latest);
        drawChart(document.getElementById("readings-chart"),readings.slice(-120));
        drawChart(document.getElementById("minute-chart"),minutes,true);
      } catch (_) {
        document.getElementById("connection-state").textContent="Не вдалося отримати дані. Повторна спроба через 10 секунд.";
        document.getElementById("connection-state").classList.add("error");
      } finally { fetching = false; }
    }
    document.querySelectorAll("[data-series]").forEach(button=>{
      const field=button.dataset.series;
      button.classList.toggle("active",visibleSeries.has(field));
      button.setAttribute("aria-pressed",visibleSeries.has(field)?"true":"false");
      button.addEventListener("click",()=>{if(visibleSeries.has(field))visibleSeries.delete(field);else visibleSeries.add(field);try{localStorage.setItem("kiln-visible-series",JSON.stringify([...visibleSeries]));}catch(_){}button.classList.toggle("active",visibleSeries.has(field));button.setAttribute("aria-pressed",visibleSeries.has(field)?"true":"false");redraw();});
    });
    refresh();
    setInterval(refresh,10000);
    setInterval(updateTimers,1000);
    window.addEventListener("resize",redraw);
    document.addEventListener("visibilitychange",()=>{if(!document.hidden)refresh();});
  </script>
</body>
</html>
