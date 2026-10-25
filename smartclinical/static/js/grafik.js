// Kucuk SVG grafik yardimcilari. Harici kutuphane kullanmiyoruz: on-prem kurulumda
// internet yok ve Chart.js'in boyutu bu is icin gereksiz.
(function () {
  function olustur(ad, attrs) {
    var e = document.createElementNS("http://www.w3.org/2000/svg", ad);
    for (var k in attrs) e.setAttribute(k, attrs[k]);
    return e;
  }

  // cizgi grafigi: seriler = [{ad, renk, degerler:[..]}], etiketler = [..]
  function cizgi(hedef, etiketler, seriler, secenek) {
    secenek = secenek || {};
    var W = 600, H = 190, sol = 36, alt = 24, ust = 8, sag = 8;
    var svg = olustur("svg", { viewBox: "0 0 " + W + " " + H, preserveAspectRatio: "none" });
    var maks = 0;
    seriler.forEach(function (s) { s.degerler.forEach(function (v) { if (v != null && v > maks) maks = v; }); });
    if (secenek.maks) maks = Math.max(maks, secenek.maks);
    maks = maks || 1;
    var n = etiketler.length;
    function x(i) { return sol + (W - sol - sag) * (n > 1 ? i / (n - 1) : 0); }
    function y(v) { return ust + (H - ust - alt) * (1 - v / maks); }
    // yatay kilavuz
    for (var g = 0; g <= 4; g++) {
      var yy = ust + (H - ust - alt) * g / 4;
      svg.appendChild(olustur("line", { x1: sol, x2: W - sag, y1: yy, y2: yy, stroke: "#e6e8ec", "stroke-width": 1 }));
      var t = olustur("text", { x: sol - 4, y: yy + 4, "font-size": 10, fill: "#7a808c", "text-anchor": "end" });
      t.textContent = Math.round(maks * (1 - g / 4));
      svg.appendChild(t);
    }
    etiketler.forEach(function (e, i) {
      if (n > 12 && i % Math.ceil(n / 12) !== 0) return;
      var t = olustur("text", { x: x(i), y: H - 6, "font-size": 10, fill: "#7a808c", "text-anchor": "middle" });
      t.textContent = e; svg.appendChild(t);
    });
    seriler.forEach(function (s) {
      var d = "";
      s.degerler.forEach(function (v, i) { if (v == null) return; d += (d ? " L" : "M") + x(i) + " " + y(v); });
      svg.appendChild(olustur("path", { d: d, fill: "none", stroke: s.renk, "stroke-width": s.kesik ? 1.5 : 2, "stroke-dasharray": s.kesik ? "5,4" : "" }));
      if (s.alan) {
        svg.appendChild(olustur("path", { d: d + " L" + x(s.degerler.length - 1) + " " + y(0) + " L" + x(0) + " " + y(0) + " Z", fill: s.renk, opacity: 0.08 }));
      }
    });
    if (secenek.bant) { // guven bandi: {alt:[..], ust:[..]}
      var d2 = "";
      secenek.bant.ust.forEach(function (v, i) { d2 += (d2 ? " L" : "M") + x(i) + " " + y(v); });
      for (var i = secenek.bant.alt.length - 1; i >= 0; i--) d2 += " L" + x(i) + " " + y(secenek.bant.alt[i]);
      svg.appendChild(olustur("path", { d: d2 + " Z", fill: secenek.bant.renk || "#0e8a8a", opacity: 0.12 }));
    }
    hedef.innerHTML = ""; hedef.appendChild(svg);
  }

  // yatay cubuk: satirlar = [{etiket, deger, renk}], maks
  function yatayCubuk(hedef, satirlar, maks) {
    maks = maks || Math.max.apply(null, satirlar.map(function (s) { return s.deger; })) || 1;
    var html = "";
    satirlar.forEach(function (s) {
      var w = Math.max(1, Math.round(100 * s.deger / maks));
      html += '<div style="display:flex;align-items:center;gap:8px;margin:3px 0;font-size:12px">' +
        '<div style="width:150px;color:#3d4350;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="' + s.etiket + '">' + s.etiket + '</div>' +
        '<div style="flex:1;background:#e6e8ec;border-radius:3px;height:12px"><div style="width:' + w + '%;height:100%;background:' + (s.renk || "#0e8a8a") + ';border-radius:3px"></div></div>' +
        '<div style="width:46px;text-align:right;font-variant-numeric:tabular-nums">' + s.deger + '</div></div>';
    });
    hedef.innerHTML = html;
  }

  // uygulama.css ile ayni renk duzeni; kategoriler sabit sirayla alir, dondurulmez
  var RENKLER = ["#16325c", "#0e8a8a", "#b7791f", "#b23a3a", "#2e7d4f", "#7a808c"];

  function metin(svg, x, y, s, attrs) {
    var t = olustur("text", attrs || {});
    t.setAttribute("x", x); t.setAttribute("y", y);
    if (!t.getAttribute("font-size")) t.setAttribute("font-size", 10);
    if (!t.getAttribute("fill")) t.setAttribute("fill", "#7a808c");
    t.textContent = s; svg.appendChild(t);
    return t;
  }

  // dikey cubuk: etiketler = [..], seriler = [{ad, renk, degerler:[..]}], secenek.yigili
  // (eski cagri bicimi cubuk(hedef, satirlar, maks) yatay cubuga yonlenir)
  function cubuk(hedef, etiketler, seriler, secenek) {
    if (!Array.isArray(seriler)) return yatayCubuk(hedef, etiketler, seriler);
    secenek = secenek || {};
    var W = 600, H = 190, sol = 36, alt = 24, ust = 8, sag = 8, n = etiketler.length;
    var svg = olustur("svg", { viewBox: "0 0 " + W + " " + H, preserveAspectRatio: "none" });
    var maks = 0;
    for (var i = 0; i < n; i++) {
      var toplam = 0, tek = 0;
      seriler.forEach(function (s) { var v = s.degerler[i] || 0; toplam += v; if (v > tek) tek = v; });
      var aday = secenek.yigili ? toplam : tek;
      if (aday > maks) maks = aday;
    }
    maks = maks || 1;
    function y(v) { return ust + (H - ust - alt) * (1 - v / maks); }
    for (var g = 0; g <= 4; g++) {
      var yy = ust + (H - ust - alt) * g / 4;
      svg.appendChild(olustur("line", { x1: sol, x2: W - sag, y1: yy, y2: yy, stroke: "#e6e8ec", "stroke-width": 1 }));
      metin(svg, sol - 4, yy + 4, Math.round(maks * (1 - g / 4)), { "text-anchor": "end" });
    }
    var grupG = (W - sol - sag) / Math.max(n, 1), genislik = Math.min(60, grupG * 0.6);
    var altG = secenek.yigili ? genislik : genislik / seriler.length;
    etiketler.forEach(function (e, i) {
      var xm = sol + grupG * i + grupG / 2;
      metin(svg, xm, H - 6, e, { "text-anchor": "middle" });
      var biriken = 0;
      seriler.forEach(function (s, j) {
        var v = s.degerler[i] || 0;
        if (!v) return;
        var renk = s.renk || RENKLER[j % RENKLER.length];
        var x0 = secenek.yigili ? xm - genislik / 2 : xm - genislik / 2 + altG * j;
        var y1 = secenek.yigili ? y(biriken + v) : y(v), y0 = secenek.yigili ? y(biriken) : y(0);
        svg.appendChild(olustur("rect", { x: x0, y: y1, width: altG - 2, height: Math.max(1, y0 - y1 - (secenek.yigili ? 1 : 0)), fill: renk }));
        if (y0 - y1 > 12) metin(svg, x0 + (altG - 2) / 2, (y0 + y1) / 2 + 3.5, v, { "text-anchor": "middle", fill: "#fff", "font-size": 10 });
        biriken += v;
      });
    });
    hedef.innerHTML = ""; hedef.appendChild(svg);
    if (seriler.length > 1) {
      var ac = document.createElement("div"); ac.className = "grafik-aciklama";
      seriler.forEach(function (s, j) {
        var sp = document.createElement("span");
        sp.innerHTML = '<i style="background:' + (s.renk || RENKLER[j % RENKLER.length]) + '"></i>';
        sp.appendChild(document.createTextNode(s.ad)); ac.appendChild(sp);
      });
      hedef.parentNode.insertBefore(ac, hedef.nextSibling);
    }
  }

  // kutu grafigi: gruplar = [{ad, min, c1, medyan, c3, maks, aykiri:[..]}]; degerler sunucuda hesaplanir
  function kutu(hedef, gruplar) {
    var W = 600, H = 190, sol = 40, alt = 24, ust = 8, sag = 8, n = gruplar.length;
    var svg = olustur("svg", { viewBox: "0 0 " + W + " " + H, preserveAspectRatio: "none" });
    var lo = Infinity, hi = -Infinity;
    gruplar.forEach(function (g) {
      [g.min, g.maks].concat(g.aykiri || []).forEach(function (v) { if (v < lo) lo = v; if (v > hi) hi = v; });
    });
    if (!isFinite(lo)) { lo = 0; hi = 1; }
    if (hi === lo) { hi = lo + 1; }
    var pay = (hi - lo) * 0.05; lo -= pay; hi += pay;
    function y(v) { return ust + (H - ust - alt) * (1 - (v - lo) / (hi - lo)); }
    for (var g = 0; g <= 4; g++) {
      var yy = ust + (H - ust - alt) * g / 4, deger = hi - (hi - lo) * g / 4;
      svg.appendChild(olustur("line", { x1: sol, x2: W - sag, y1: yy, y2: yy, stroke: "#e6e8ec", "stroke-width": 1 }));
      metin(svg, sol - 4, yy + 4, Math.round(deger * 10) / 10, { "text-anchor": "end" });
    }
    var grupG = (W - sol - sag) / Math.max(n, 1), genislik = Math.min(70, grupG * 0.5);
    gruplar.forEach(function (k, i) {
      var xm = sol + grupG * i + grupG / 2, renk = k.renk || RENKLER[i % RENKLER.length];
      metin(svg, xm, H - 6, k.ad + (k.n ? " (n=" + k.n + ")" : ""), { "text-anchor": "middle" });
      svg.appendChild(olustur("line", { x1: xm, x2: xm, y1: y(k.maks), y2: y(k.c3), stroke: renk, "stroke-width": 1.5 }));
      svg.appendChild(olustur("line", { x1: xm, x2: xm, y1: y(k.c1), y2: y(k.min), stroke: renk, "stroke-width": 1.5 }));
      [k.min, k.maks].forEach(function (v) {
        svg.appendChild(olustur("line", { x1: xm - genislik / 4, x2: xm + genislik / 4, y1: y(v), y2: y(v), stroke: renk, "stroke-width": 1.5 }));
      });
      svg.appendChild(olustur("rect", { x: xm - genislik / 2, y: y(k.c3), width: genislik, height: Math.max(1, y(k.c1) - y(k.c3)), fill: renk, opacity: 0.18, stroke: renk, "stroke-width": 1.5 }));
      svg.appendChild(olustur("line", { x1: xm - genislik / 2, x2: xm + genislik / 2, y1: y(k.medyan), y2: y(k.medyan), stroke: renk, "stroke-width": 2.5 }));
      (k.aykiri || []).forEach(function (v) {
        svg.appendChild(olustur("circle", { cx: xm, cy: y(v), r: 3, fill: "#fff", stroke: renk, "stroke-width": 1.5 }));
      });
    });
    hedef.innerHTML = ""; hedef.appendChild(svg);
  }

  window.SCGrafik = { cizgi: cizgi, cubuk: cubuk, kutu: kutu, renkler: RENKLER };
})();
