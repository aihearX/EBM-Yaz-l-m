// eCRF: tasarimci tablosu (satir ekle/sil/tasi, JSON'a cevir) ve veri giris formunda kosullu alanlar
document.addEventListener("DOMContentLoaded", function () {
  var tasarimci = document.getElementById("tasarimci");
  if (tasarimci) tasarimciKur(tasarimci);
  if (document.querySelector("[data-kosul-alan]")) kosulKur();
});

function tasarimciKur(form) {
  var govde = document.querySelector("#alan-tablo tbody");
  var sablon = document.getElementById("alan-satir");
  var gizli = document.getElementById("alanlar_json");
  var bos = document.getElementById("alan-bos");
  var kilitli = form.getAttribute("data-degistirilebilir") === "0";
  var baslangic = [];
  try { baslangic = JSON.parse(gizli.value || "[]"); } catch (e) { baslangic = []; }
  var eskiKodlar = {};
  baslangic.forEach(function (a) { if (a.kod) eskiKodlar[a.kod] = a.tip; });

  function deger(tr, k) { return tr.querySelector('[data-k="' + k + '"]'); }

  function satirEkle(a) {
    a = a || {};
    var tr = sablon.content.firstElementChild.cloneNode(true);
    deger(tr, "kod").value = a.kod || "";
    deger(tr, "etiket").value = a.etiket || "";
    deger(tr, "tip").value = a.tip || "metin";
    deger(tr, "zorunlu").checked = !!a.zorunlu;
    deger(tr, "birim").value = a.birim || "";
    deger(tr, "min").value = a.min === undefined || a.min === null ? "" : a.min;
    deger(tr, "max").value = a.max === undefined || a.max === null ? "" : a.max;
    deger(tr, "secenekler").value = (a.secenekler || []).join("; ");
    deger(tr, "bolum").value = a.bolum || "";
    deger(tr, "kosul_alan").value = a.kosul && a.kosul.alan ? a.kosul.alan : "";
    deger(tr, "kosul_deger").value = a.kosul && a.kosul.deger !== undefined ? a.kosul.deger : "";
    deger(tr, "cdash").value = a.cdash || "";
    // kaydi olan formda mevcut alanlarin kodu/tipi degistirilemez, satir silinemez
    if (kilitli && a.kod && eskiKodlar[a.kod] !== undefined) {
      deger(tr, "kod").readOnly = true;
      deger(tr, "tip").disabled = true;
      tr.querySelector('[data-islem="sil"]').disabled = true;
      tr.setAttribute("data-kilitli", "1");
    }
    tipDegisti(tr);
    deger(tr, "tip").addEventListener("change", function () { tipDegisti(tr); });
    govde.appendChild(tr);
    numarala();
    return tr;
  }

  function tipDegisti(tr) {
    var tip = deger(tr, "tip").value;
    var sec = deger(tr, "secenekler");
    var sayisal = tip === "sayi";
    sec.disabled = !(tip === "secim" || tip === "coklu_secim");
    if (tip === "evet_hayir") { sec.value = "Evet; Hayır"; }
    deger(tr, "min").disabled = !sayisal;
    deger(tr, "max").disabled = !sayisal;
    deger(tr, "birim").disabled = !sayisal && tip !== "metin";
  }

  function numarala() {
    var satirlar = govde.querySelectorAll("tr");
    satirlar.forEach(function (tr, i) { tr.querySelector(".sira").textContent = i + 1; });
    bos.style.display = satirlar.length ? "none" : "";
  }

  function topla() {
    var liste = [];
    govde.querySelectorAll("tr").forEach(function (tr) {
      var tip = deger(tr, "tip").value;
      var a = {
        kod: deger(tr, "kod").value.trim().toUpperCase(),
        etiket: deger(tr, "etiket").value.trim(),
        tip: tip,
        zorunlu: deger(tr, "zorunlu").checked,
        birim: deger(tr, "birim").value.trim(),
        min: deger(tr, "min").value.trim(),
        max: deger(tr, "max").value.trim(),
        secenekler: deger(tr, "secenekler").value,
        bolum: deger(tr, "bolum").value.trim(),
        cdash: deger(tr, "cdash").value.trim()
      };
      var ka = deger(tr, "kosul_alan").value.trim().toUpperCase();
      if (ka) a.kosul = { alan: ka, deger: deger(tr, "kosul_deger").value.trim() };
      liste.push(a);
    });
    return liste;
  }

  govde.addEventListener("click", function (e) {
    var b = e.target.closest("button[data-islem]");
    if (!b) return;
    var tr = b.closest("tr");
    var islem = b.getAttribute("data-islem");
    if (islem === "sil") {
      if (tr.getAttribute("data-kilitli") === "1") return;
      tr.remove();
    } else if (islem === "yukari" && tr.previousElementSibling) {
      govde.insertBefore(tr, tr.previousElementSibling);
    } else if (islem === "asagi" && tr.nextElementSibling) {
      govde.insertBefore(tr.nextElementSibling, tr);
    }
    numarala();
  });
  document.getElementById("alan-ekle").addEventListener("click", function () {
    var tr = satirEkle({});
    deger(tr, "kod").focus();
  });
  form.addEventListener("submit", function () {
    gizli.value = JSON.stringify(topla());
    // devre disi select'ler gonderilmez ama JSON'a zaten yazildi
  });

  baslangic.forEach(satirEkle);
  numarala();
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
