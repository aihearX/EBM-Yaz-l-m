// eCRF: tasarimci (temel tablo + ayrinti paneli + canli onizleme) ve veri giris formunda kosullu alanlar
document.addEventListener("DOMContentLoaded", function () {
  var tasarimci = document.getElementById("tasarimci");
  if (tasarimci) tasarimciKur(tasarimci);
  if (document.querySelector("[data-kosul-alan]")) kosulKur();
});

var TR_HARF = { "ç": "C", "Ç": "C", "ğ": "G", "Ğ": "G", "ı": "I", "I": "I", "i": "I", "İ": "I", "ö": "O", "Ö": "O", "ş": "S", "Ş": "S", "ü": "U", "Ü": "U" };

// "Sistolik kan basıncı" -> "SISTOLIKKANBASIN" (en cok 16 karakter, harfle baslar)
function kodUret(etiket, enCok) {
  enCok = enCok || 16;
  var s = String(etiket || "").replace(/[çÇğĞıIiİöÖşŞüÜ]/g, function (h) { return TR_HARF[h] || h; });
  s = s.toUpperCase().replace(/[^A-Z0-9]+/g, "");
  if (!s) return "";
  if (/^[0-9]/.test(s)) s = "A" + s;
  return s.slice(0, enCok);
}

function tasarimciKur(form) {
  var govde = document.querySelector("#alan-tablo tbody");
  var sablon = document.getElementById("alan-satir");
  var gizli = document.getElementById("alanlar_json");
  var bos = document.getElementById("alan-bos");
  var panel = document.getElementById("alan-ayrinti");
  var panelKod = document.getElementById("ayrinti-kod");
  var panelToplam = document.getElementById("ayrinti-toplam");
  var kodListesi = document.getElementById("kod-listesi");
  var onizleme = document.getElementById("onizleme");
  var formAd = document.getElementById("form-ad");
  var formKod = document.getElementById("form-kod");
  var kilitli = form.getAttribute("data-degistirilebilir") === "0";
  var secili = null;
  var baslangic = [];
  try { baslangic = JSON.parse(gizli.value || "[]"); } catch (e) { baslangic = []; }
  var eskiKodlar = {};
  baslangic.forEach(function (a) { if (a.kod) eskiKodlar[a.kod] = a.tip; });

  function deger(tr, k) { return tr.querySelector('[data-k="' + k + '"]'); }
  function tipAdi(tip) {
    var sec = govde.querySelector('select[data-k="tip"]') || sablon.content.querySelector('select[data-k="tip"]');
    var o = sec && sec.querySelector('option[value="' + tip + '"]');
    return o ? o.textContent : tip;
  }

  // form kodu addan uretilir; kullanici elle yazdiysa dokunulmaz
  if (formAd && formKod) {
    if (formKod.value) formKod.setAttribute("data-elle", "1");
    formAd.addEventListener("input", function () {
      if (formKod.getAttribute("data-elle") !== "1") formKod.value = kodUret(formAd.value, 16);
    });
    formKod.addEventListener("input", function () { formKod.setAttribute("data-elle", formKod.value ? "1" : "0"); });
  }

  function tekilKod(kod, tr) {
    if (!kod) return kod;
    var mevcut = {};
    govde.querySelectorAll("tr").forEach(function (x) { if (x !== tr) mevcut[deger(x, "kod").value.trim().toUpperCase()] = 1; });
    var aday = kod, i = 2;
    while (mevcut[aday]) { aday = kod.slice(0, 16 - String(i).length) + i; i += 1; }
    return aday;
  }

  function satirEkle(a, odak) {
    a = a || {};
    var tr = sablon.content.firstElementChild.cloneNode(true);
    tr.ek = {
      bolum: a.bolum || "",
      kosul_alan: a.kosul && a.kosul.alan ? a.kosul.alan : "",
      kosul_deger: a.kosul && a.kosul.deger !== undefined ? a.kosul.deger : "",
      cdash: a.cdash || "",
      toplam: Array.isArray(a.toplam) ? a.toplam.join(", ") : (a.toplam || "")
    };
    deger(tr, "kod").value = a.kod || "";
    if (a.kod) tr.setAttribute("data-elle", "1");
    deger(tr, "etiket").value = a.etiket || "";
    deger(tr, "tip").value = a.tip || "metin";
    deger(tr, "zorunlu").checked = !!a.zorunlu;
    deger(tr, "birim").value = a.birim || "";
    deger(tr, "min").value = a.min === undefined || a.min === null ? "" : a.min;
    deger(tr, "max").value = a.max === undefined || a.max === null ? "" : a.max;
    var sec = a.secenekler;
    if (typeof sec === "string") sec = sec.split(/[;\n]/);
    deger(tr, "secenekler").value = (sec || []).map(function (s) { return String(s).trim(); }).filter(Boolean).join("\n");
    // kaydi olan formda mevcut alanlarin kodu/tipi degistirilemez, satir silinemez
    if (kilitli && a.kod && eskiKodlar[a.kod] !== undefined) {
      deger(tr, "kod").readOnly = true;
      deger(tr, "tip").disabled = true;
      tr.querySelector('[data-islem="sil"]').disabled = true;
      tr.setAttribute("data-kilitli", "1");
    }
    tipDegisti(tr);
    deger(tr, "tip").addEventListener("change", function () { tipDegisti(tr); yenile(); });
    deger(tr, "etiket").addEventListener("input", function () {
      if (tr.getAttribute("data-elle") !== "1") deger(tr, "kod").value = tekilKod(kodUret(this.value), tr);
      yenile();
    });
    deger(tr, "kod").addEventListener("input", function () {
      tr.setAttribute("data-elle", this.value ? "1" : "0");
      if (secili === tr) panelKod.textContent = this.value.toUpperCase() || "—";
      yenile();
    });
    tr.addEventListener("focusin", function () { sec_(tr); });
    tr.addEventListener("input", yenile);
    tr.addEventListener("change", yenile);
    govde.appendChild(tr);
    numarala();
    if (odak) { sec_(tr); deger(tr, "etiket").focus(); }
    return tr;
  }

  function tipDegisti(tr) {
    var tip = deger(tr, "tip").value;
    var ek = tr.querySelector("td.ek");
    if (tip === "secim" || tip === "coklu_secim") ek.setAttribute("data-gorunum", "secim");
    else if (tip === "sayi") ek.setAttribute("data-gorunum", "sayi");
    else ek.setAttribute("data-gorunum", "yok");
    if (tip === "evet_hayir") tr.querySelector(".ek-yok").textContent = "Evet / Hayır";
    else tr.querySelector(".ek-yok").textContent = "—";
    if (secili === tr) panelToplam.hidden = tip !== "sayi";
  }

  function numarala() {
    var satirlar = govde.querySelectorAll("tr");
    satirlar.forEach(function (tr, i) { tr.querySelector(".sira").textContent = i + 1; });
    bos.style.display = satirlar.length ? "none" : "";
  }

  // --- ayrinti paneli ---------------------------------------------------
  function sec_(tr) {
    if (secili === tr) return;
    if (secili) secili.classList.remove("secili");
    secili = tr;
    tr.classList.add("secili");
    panel.hidden = false;
    panelKod.textContent = deger(tr, "kod").value.toUpperCase() || "—";
    panel.querySelectorAll("[data-p]").forEach(function (g) { g.value = tr.ek[g.getAttribute("data-p")] || ""; });
    panelToplam.hidden = deger(tr, "tip").value !== "sayi";
    kodListesi.innerHTML = "";
    govde.querySelectorAll("tr").forEach(function (x) {
      var k = deger(x, "kod").value.trim().toUpperCase();
      if (k && x !== tr) { var o = document.createElement("option"); o.value = k; kodListesi.appendChild(o); }
    });
  }
  panel.querySelectorAll("[data-p]").forEach(function (g) {
    g.addEventListener("input", function () {
      if (!secili) return;
      secili.ek[g.getAttribute("data-p")] = g.value;
      yenile();
    });
  });
  document.getElementById("ayrinti-kapat").addEventListener("click", function () {
    if (secili) secili.classList.remove("secili");
    secili = null;
    panel.hidden = true;
  });

  // --- toplama ve onizleme ----------------------------------------------
  function satirOku(tr) {
    var tip = deger(tr, "tip").value;
    var a = {
      kod: deger(tr, "kod").value.trim().toUpperCase(),
      etiket: deger(tr, "etiket").value.trim(),
      tip: tip,
      zorunlu: deger(tr, "zorunlu").checked,
      birim: deger(tr, "birim").value.trim(),
      min: deger(tr, "min").value.trim(),
      max: deger(tr, "max").value.trim(),
      secenekler: deger(tr, "secenekler").value.split(/[\n;]/).map(function (s) { return s.trim(); }).filter(Boolean),
      bolum: (tr.ek.bolum || "").trim(),
      cdash: (tr.ek.cdash || "").trim()
    };
    var ka = (tr.ek.kosul_alan || "").trim().toUpperCase();
    if (ka) a.kosul = { alan: ka, deger: (tr.ek.kosul_deger || "").trim() };
    var toplam = (tr.ek.toplam || "").split(/[,;\s]+/).map(function (s) { return s.trim().toUpperCase(); }).filter(Boolean);
    if (tip === "sayi" && toplam.length) a.toplam = toplam;
    return a;
  }

  function topla() {
    var liste = [];
    govde.querySelectorAll("tr").forEach(function (tr) { liste.push(satirOku(tr)); });
    return liste;
  }

  function metin(s) { var d = document.createElement("div"); d.textContent = s; return d.innerHTML; }

  function onizle() {
    var liste = topla();
    if (!liste.length) { onizleme.innerHTML = '<p class="onz-bos">Alan eklendikçe burada görünür.</p>'; return; }
    var h = "", bolum = null;
    liste.forEach(function (a) {
      if (a.bolum && a.bolum !== bolum) { bolum = a.bolum; h += "<h4>" + metin(bolum) + "</h4>"; }
      var ornek;
      if (a.tip === "secim" || a.tip === "coklu_secim") ornek = (a.secenekler.length ? a.secenekler.slice(0, 4).join(" · ") : "seçenek yok") + (a.secenekler.length > 4 ? " …" : "");
      else if (a.tip === "evet_hayir") ornek = "Evet · Hayır";
      else if (a.tip === "sayi") ornek = (a.toplam ? "otomatik toplam" : "sayı") + (a.birim ? " (" + a.birim + ")" : "") + (a.min !== "" || a.max !== "" ? " " + (a.min || "…") + "–" + (a.max || "…") : "");
      else if (a.tip === "tarih") ornek = "gg.aa.yyyy";
      else if (a.tip === "metin_uzun") ornek = "uzun metin";
      else ornek = "metin";
      h += '<div class="onz-alan"><label>' + metin(a.etiket || "(etiket yok)") + (a.zorunlu ? " *" : "") + ' <small style="font-weight:400;color:#6b7a90">' + metin(a.kod || "") + "</small></label>"
        + '<span class="onz-girdi">' + metin(tipAdi(a.tip)) + " · " + metin(ornek) + "</span>"
        + (a.kosul ? '<div class="onz-kosul">yalnızca ' + metin(a.kosul.alan) + " = " + metin(a.kosul.deger || "") + " ise</div>" : "")
        + "</div>";
    });
    onizleme.innerHTML = h;
  }

  var zamanlayici = null;
  function yenile() {
    clearTimeout(zamanlayici);
    zamanlayici = setTimeout(onizle, 120);
  }

  // --- olaylar ------------------------------------------------------------
  govde.addEventListener("click", function (e) {
    var b = e.target.closest("button[data-islem]");
    if (!b) return;
    var tr = b.closest("tr");
    var islem = b.getAttribute("data-islem");
    if (islem === "ayrinti") {
      sec_(tr);
      panel.querySelector("[data-p]").focus();
      return;
    }
    if (islem === "sil") {
      if (tr.getAttribute("data-kilitli") === "1") return;
      if (secili === tr) { secili = null; panel.hidden = true; }
      tr.remove();
    } else if (islem === "yukari" && tr.previousElementSibling) {
      govde.insertBefore(tr, tr.previousElementSibling);
    } else if (islem === "asagi" && tr.nextElementSibling) {
      govde.insertBefore(tr.nextElementSibling, tr);
    }
    numarala();
    yenile();
  });
  document.getElementById("alan-ekle").addEventListener("click", function () { satirEkle({}, true); yenile(); });
  document.querySelectorAll("[data-hizli]").forEach(function (b) {
    b.addEventListener("click", function () {
      var tip = b.getAttribute("data-hizli");
      var a = { tip: tip };
      if (tip === "tarih") a.etiket = "Tarih";
      if (tip === "sayi") a.birim = "";
      var tr = satirEkle(a, true);
      if (a.etiket) deger(tr, "kod").value = tekilKod(kodUret(a.etiket), tr);
      yenile();
    });
  });
  form.addEventListener("submit", function () {
    gizli.value = JSON.stringify(topla());
    // devre disi select'ler gonderilmez ama JSON'a zaten yazildi
  });

  baslangic.forEach(function (a) { satirEkle(a, false); });
  numarala();
  onizle();
}

// Veri giris formu: data-kosul-alan / data-kosul-deger tasiyan alanlar kosul saglaninca gorunur
function kosulKur() {
  var alanlar = document.querySelectorAll("[data-kosul-alan]");

  function kaynakDeger(kod) {
    var girdiler = document.querySelectorAll('[name="' + kod + '"]');
    if (!girdiler.length) return "";
    var ilk = girdiler[0];
    if (ilk.type === "radio") {
      for (var i = 0; i < girdiler.length; i++) if (girdiler[i].checked) return girdiler[i].value;
      return "";
    }
    if (ilk.type === "checkbox") {
      var secili = [];
      for (var j = 0; j < girdiler.length; j++) if (girdiler[j].checked) secili.push(girdiler[j].value);
      return secili;
    }
    return ilk.value;
  }

  function uygula() {
    alanlar.forEach(function (el) {
      var v = kaynakDeger(el.getAttribute("data-kosul-alan"));
      var hedef = el.getAttribute("data-kosul-deger") || "";
      var ok = Array.isArray(v) ? v.indexOf(hedef) >= 0 : String(v) === hedef;
      el.style.display = ok ? "" : "none";
      el.querySelectorAll("input,select,textarea").forEach(function (g) {
        if (g.hasAttribute("data-zorunlu")) g.required = ok;
      });
    });
  }
  document.addEventListener("change", uygula);
  document.addEventListener("input", uygula);
  uygula();
}
