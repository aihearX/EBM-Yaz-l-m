// Ortak arayuz davranislari
document.addEventListener("DOMContentLoaded", function () {
  // onay isteyen formlar
  document.querySelectorAll("form[data-onay]").forEach(function (f) {
    f.addEventListener("submit", function (e) { if (!confirm(f.getAttribute("data-onay"))) e.preventDefault(); });
  });
  // oturum zaman asimi uyarisi (sunucu tarafi max_age ile uyumlu, 30 dk)
  var sure = parseInt(document.body.getAttribute("data-oturum-dk") || "30", 10);
  var zaman = setTimeout(function () {
    if (confirm("Oturumunuz hareketsizlik nedeniyle sona ermek üzere. Devam etmek istiyor musunuz?")) location.reload();
    else location.href = "/cikis";
  }, (sure - 1) * 60 * 1000);
  // mesaj kutusunu kapat
  document.querySelectorAll(".mesaj").forEach(function (m) { m.addEventListener("click", function () { m.style.display = "none"; }); });
});
