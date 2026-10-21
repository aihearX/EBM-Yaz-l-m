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
  function cubuk(hedef, satirlar, maks) {
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

  window.SCGrafik = { cizgi: cizgi, cubuk: cubuk };
})();
