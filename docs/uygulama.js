/* Olist müşteri rotası — tarayıcıda çalışan, kurulum gerektirmeyen analiz uygulaması.
   Veri: veri.js (window.OLIST). Grafikler doğrudan SVG ile çizilir; dış kütüphane yok. */
(function () {
  "use strict";
  const V = window.OLIST;
  if (!V) { document.body.innerHTML = "<p style='padding:40px'>veri.js bulunamadı. Dosyanın index.html ile aynı klasörde olduğundan emin olun.</p>"; return; }
  const O = V.ozet;
  const M = V.musteri;
  const N = M.ay.length;

  /* ---------------- biçimlendirme ---------------- */
  const sayiF = new Intl.NumberFormat("tr-TR");
  const sayi = (x) => sayiF.format(Math.round(x));
  const ondalik = (x, d = 1) => new Intl.NumberFormat("tr-TR", { minimumFractionDigits: d, maximumFractionDigits: d }).format(x);
  const yuzde = (x, d = 1) => "%" + ondalik(x, d);
  const milyon = (x, d = 2) => ondalik(x / 1e6, d);
  const bin = (x) => sayi(x / 1000);
  const ayAdlari = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"];
  const ayUzun = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"];
  const ayEtiket = (s, uzun) => { const [y, m] = s.split("-"); return (uzun ? ayUzun : ayAdlari)[+m - 1] + " " + y; };
  const tarihKisa = (s) => { const [y, m, g] = s.split("-"); return +g + " " + ayAdlari[+m - 1] + " " + y.slice(2); };

  // Sayıdan sonra gelen iyelik eki (98’i, 2’si, %54,9’u). Sayının okunuşundaki son kelimeye göre.
  function iyelik(metin) {
    const d = String(metin).replace(/[^0-9]/g, "");
    if (!d) return "’i";
    const birler = { 1: "i", 2: "si", 3: "ü", 4: "ü", 5: "i", 6: "sı", 7: "si", 8: "i", 9: "u" };
    const onlar = { 1: "u", 2: "si", 3: "u", 4: "ı", 5: "si", 6: "ı", 7: "i", 8: "i", 9: "ı" };
    const son = +d[d.length - 1];
    if (son) return "’" + birler[son];
    if (d.length === 1) return "’ı";
    const o = +d[d.length - 2];
    if (o) return "’" + onlar[o];
    if (d.length >= 4 && d.slice(-3) === "000") return "’i";
    return "’ü";
  }
  // -de / -da bulunma eki (90 günde zaten metinde)  — yalnızca gerektiğinde

  const $ = (s, k = document) => k.querySelector(s);
  function el(tag, attrs = {}, ...cocuk) {
    const e = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) {
      if (v == null || v === false) continue;
      if (k === "html") e.innerHTML = v; else if (k === "class") e.className = v; else e.setAttribute(k, v);
    }
    for (const c of cocuk.flat()) if (c != null) e.append(c instanceof Node ? c : document.createTextNode(c));
    return e;
  }
  const NS = "http://www.w3.org/2000/svg";
  function S(tag, attrs = {}, ...cocuk) {
    const e = document.createElementNS(NS, tag);
    for (const [k, v] of Object.entries(attrs)) if (v != null) e.setAttribute(k, v);
    for (const c of cocuk.flat()) if (c != null) e.append(c instanceof Node ? c : document.createTextNode(c));
    return e;
  }
  const svgKok = (w, h, etiket) => S("svg", { viewBox: `0 0 ${w} ${h}`, role: "img", "aria-label": etiket });
  const metin = (x, y, t, a = {}) => S("text", Object.assign({ x, y }, a), t);

  /* ---------------- ipucu ---------------- */
  const ip = $("#ipucu");
  document.addEventListener("pointermove", (e) => {
    const h = e.target.closest && e.target.closest("[data-ipucu]");
    if (!h) { ip.hidden = true; return; }
    ip.innerHTML = h.getAttribute("data-ipucu");
    ip.hidden = false;
    const r = ip.getBoundingClientRect();
    let x = e.clientX + 14, y = e.clientY + 14;
    if (x + r.width > innerWidth - 8) x = e.clientX - r.width - 14;
    if (y + r.height > innerHeight - 8) y = e.clientY - r.height - 14;
    ip.style.left = x + "px"; ip.style.top = y + "px";
  });
  document.addEventListener("scroll", () => { ip.hidden = true; }, { passive: true });

  /* ---------------- renkler ---------------- */
  const R = { mata: "#0F3D2E", mata2: "#1D5A45", yaprak: "#5E8F76", filiz: "#B7CDBF", sis: "#EEF2EC", ipe: "#F2C230", rosa: "#C93A7B", tinta: "#13221C", musgo: "#536A5F", cizgi: "#D3DDD5" };
  const SEG = V.segmentler;
  const SEG_RENK = ["#F2C230", "#C93A7B", "#0F3D2E", "#3E7A5E", "#8DB4A0", "#4E5F84", "#B5BDCB"];
  const KISA = ["Şampiyon", "Uyuyan sadık", "Yeni, yüksek", "Yeni, standart", "Soğuyan", "Kayıp, yüksek", "Kayıp, standart"];
  const SEG_YAZI = ["#13221C", "#FFFFFF", "#FFFFFF", "#FFFFFF", "#13221C", "#FFFFFF", "#13221C"];
  function yesilOlcek(t) { // 0..1 → açık sisten koyu mataya
    t = Math.max(0, Math.min(1, t));
    const a = [238, 242, 236], b = [15, 61, 46];
    const g = Math.pow(t, 0.75);
    return `rgb(${a.map((v, i) => Math.round(v + (b[i] - v) * g)).join(",")})`;
  }

  /* ---------------- RFM sınırları ve segment açıklamaları ---------------- */
  const kes = O.rfm.kesim_noktalari;
  const rS = kes.R_sinirlari_gun.map(Math.round);          // [96,180,271,386]
  const mS = kes["M_sinirlari_R$"];                        // [55.36, 87.51, 133.05, 209.12]
  const para = (x) => ondalik(x, 0);
  const R_ARALIK = { 5: `${rS[0]} gün veya daha az`, 4: `${rS[0] + 1}–${rS[1]} gün`, 3: `${rS[1] + 1}–${rS[2]} gün`, 2: `${rS[2] + 1}–${rS[3]} gün`, 1: `${rS[3]} günden fazla` };
  const M_ARALIK = { 1: `${para(mS[0])} R$ veya daha az`, 2: `${para(mS[0])}–${para(mS[1])} R$`, 3: `${para(mS[1])}–${para(mS[2])} R$`, 4: `${para(mS[2])}–${para(mS[3])} R$`, 5: `${para(mS[3])} R$’dan fazla` };
  const ESIK_M = para(mS[2]);
  const SEG_BILGI = [
    { grup: "Koru", kural: "2+ farklı günde alışveriş · son alışveriş son 180 gün içinde (R 4–5)",
      tanim: "Olist’in en sadık ve hâlâ aktif küçük çekirdeği. Birden fazla günde alışveriş yapmış ve yakın zamanda yine gelmiş.",
      oneri: "Yorum ve arkadaş tavsiyesi isteyin; yeni fikirleri önce bu grupta deneyin.", olcut: "Üçüncü alışverişe geçen müşteri payı" },
    { grup: "Geri kazan", kural: "2+ farklı günde alışveriş · son alışveriş 180 günden eski (R 1–3)",
      tanim: "Eskiden birden fazla kez gelmiş ama bir süredir sessiz. Olist’i tanıyor; neden durduğu bilinmiyor.",
      oneri: "Tek ve süreli bir geri dönüş mesajı; önce küçük bir test grubunda, kontrol grubuyla.", olcut: "Kontrol grubuna göre geri dönüş farkı" },
    { grup: "Savun", kural: `Tek gün alışveriş · son 180 gün içinde (R 4–5) · ${ESIK_M} R$’dan fazla (M 4–5)`,
      tanim: "Yeni gelmiş ve büyük sepetle alışveriş yapmış müşteriler. Ciroya katkısı en yüksek gruplardan biri.",
      oneri: "İndirim yerine, teslimattan 2–3 hafta sonra tamamlayıcı bir kategori önerin. Dönenlerin yaklaşık üçte biri ilk 30 günde dönüyor.", olcut: "180 günde tekrar alım, kontrol grubuna göre" },
    { grup: "Savun", kural: `Tek gün alışveriş · son 180 gün içinde (R 4–5) · ${ESIK_M} R$ veya daha az (M 1–3)`,
      tanim: "Yeni gelmiş, küçük ya da orta sepetli müşteriler. Sayıca en büyük gruplardan biri.",
      oneri: "Tamamlayıcı kategori önerisini maliyetsiz kanallardan (e-posta, bildirim) gönderin.", olcut: "180 günde tekrar alım, kontrol grubuna göre" },
    { grup: "Geri kazan", kural: `Tek gün alışveriş · son alışveriş ${R_ARALIK[3]} önce (R 3) · harcamaya bakılmaz`,
      tanim: "Tek alışverişten sonra altı-dokuz aydır gelmeyenler. Kaybolma eşiğindeler.",
      oneri: "Tek, süreli bir hatırlatma; önce küçük bir test hücresinde deneyin.", olcut: "Kontrol grubuna göre geri dönüş farkı" },
    { grup: "Geri kazan", kural: `Tek gün alışveriş · son alışveriş ${rS[2]} günden eski (R 1–2) · ${ESIK_M} R$’dan fazla (M 4–5)`,
      tanim: "Bir kez büyük sepetle alışveriş yapmış, sonra hiç dönmemiş müşteriler. Cironun önemli bir kısmı bu gruptan geldi.",
      oneri: "Küçük, süreli bir geri kazanım denemesi. Asıl değer: bu müşterilerin profilini yeni müşteri hedeflemesinde kullanmak.", olcut: "Kontrol grubuna göre ek ciro" },
    { grup: "Bırak", kural: `Tek gün alışveriş · son alışveriş ${rS[2]} günden eski (R 1–2) · ${ESIK_M} R$ veya daha az (M 1–3)`,
      tanim: "Bir kez küçük sepetle gelip dönmeyenler. Sayıca en büyük grup, ciro payı düşük.",
      oneri: "Ücretli kampanyalardan çıkarın, yalnızca maliyetsiz kanallarda tutun.", olcut: "Tasarruf edilen kampanya bütçesi" },
  ];

  /* ---------------- filtreler ---------------- */
  const F = { bas: 0, bit: V.aylar.length - 1, eyalet: -1, segment: -1, kategori: -1 };
  const maske = new Uint8Array(N);
  function secenekler(sel, liste, hepsi) {
    sel.innerHTML = "";
    if (hepsi) sel.append(el("option", { value: -1 }, hepsi));
    liste.forEach(([v, t]) => sel.append(el("option", { value: v }, t)));
  }
  const aySec = V.aylar.map((a, i) => [i, ayEtiket(a)]);
  secenekler($("#f-bas"), aySec); secenekler($("#f-bit"), aySec);
  $("#f-bit").value = F.bit;
  secenekler($("#f-eyalet"), V.eyaletler.map((e, i) => [i, `${e.ad} (${e.kod})`]).sort((a, b) => a[1].localeCompare(b[1], "tr")), "Tüm eyaletler");
  secenekler($("#f-segment"), SEG.map((s, i) => [i, s]), "Tüm segmentler");
  secenekler($("#f-kategori"), V.kategoriler.map((k, i) => [i, `${k.ad} (${sayi(k.musteri)})`]), "Tüm kategoriler");

  function maskeHesapla() {
    let n = 0;
    for (let i = 0; i < N; i++) {
      const ok = M.ay[i] >= F.bas && M.ay[i] <= F.bit && (F.eyalet < 0 || M.eyalet[i] === F.eyalet)
        && (F.segment < 0 || M.segment[i] === F.segment) && (F.kategori < 0 || M.kategori[i] === F.kategori);
      maske[i] = ok ? 1 : 0; n += maske[i];
    }
    return n;
  }
  function filtreDegisti() {
    F.bas = +$("#f-bas").value; F.bit = +$("#f-bit").value;
    if (F.bas > F.bit) { [F.bas, F.bit] = [F.bit, F.bas]; $("#f-bas").value = F.bas; $("#f-bit").value = F.bit; }
    F.eyalet = +$("#f-eyalet").value; F.segment = +$("#f-segment").value; F.kategori = +$("#f-kategori").value;
    ciz();
  }
  ["#f-bas", "#f-bit", "#f-eyalet", "#f-segment", "#f-kategori"].forEach((s) => $(s).addEventListener("change", filtreDegisti));
  $("#temizle").addEventListener("click", () => {
    $("#f-bas").value = 0; $("#f-bit").value = V.aylar.length - 1;
    ["#f-eyalet", "#f-segment", "#f-kategori"].forEach((s) => ($(s).value = -1));
    filtreDegisti();
  });
  const filtreVar = () => F.bas > 0 || F.bit < V.aylar.length - 1 || F.eyalet >= 0 || F.segment >= 0 || F.kategori >= 0;

  /* ---------------- 1. Başlangıç ---------------- */
  const koliKutu = $("#koliler");
  for (let i = 0; i < 100; i++) {
    const k = el("div", { class: "koli" });
    k.style.animationDelay = (i * 9) + "ms";
    koliKutu.append(k);
  }
  function girisCiz(n) {
    let tekrar = 0, ciro = 0, ciroT = 0, sip = 0;
    for (let i = 0; i < N; i++) if (maske[i]) {
      const h = M.harcama_kurus[i] / 100; ciro += h; sip += M.siparis[i];
      if (M.gun[i] >= 2) { tekrar++; ciroT += h; }
    }
    const pay = n ? tekrar / n * 100 : 0;
    const gelmeyen = n ? Math.round(100 - pay) : 0;
    const sari = n ? Math.round(pay) : 0;
    $("#giris-baslik").textContent = n ? `100 müşteriden ${gelmeyen}${iyelik(gelmeyen)} bir daha gelmedi.` : "Bu filtrelerle müşteri yok.";
    $("#giris-alt").innerHTML = n
      ? `${filtreVar() ? "Seçimdeki" : "Olist’in"} <b>${sayi(n)}</b> müşterisinin yalnızca <b>${sayi(tekrar)}${iyelik(sayi(tekrar))}</b> (${yuzde(pay)}) ilk alışverişinden sonra başka bir gün yeniden alışveriş yaptı. Bu küçük grup cironun <b>${yuzde(ciro ? ciroT / ciro * 100 : 0)}${iyelik(ondalik(ciro ? ciroT / ciro * 100 : 0))}</b> getirdi; geri kalanın neredeyse tamamı tek seferlik alışverişlerden geldi.`
      : "Filtreleri genişletin ya da temizleyin.";
    koliKutu.setAttribute("aria-label", `100 koli: ${sari} tanesi sarı, birden fazla günde alışveriş yapan müşterileri gösteriyor.`);
    [...koliKutu.children].forEach((k, i) => k.classList.toggle("don", i >= 100 - sari));
    const rk = $("#rakamlar");
    rk.innerHTML = "";
    const kalem = (dd, dt) => rk.append(el("div", {}, el("dd", { html: dd }), el("dt", {}, dt)));
    kalem(sayi(n), "müşteri");
    kalem(sayi(sip), "geçerli sipariş");
    kalem(ciro >= 1e6 ? `${milyon(ciro)}<small>milyon R$</small>` : `${sayi(ciro / 1000)}<small>bin R$</small>`, "ciro, kargo dahil");
    kalem(sip ? `${sayi(ciro / sip)}<small>R$</small>` : "–", "ortalama sipariş tutarı");
  }

  /* ---------------- 2. Kohort ısı haritası ---------------- */
  const AY0 = V.aylar.indexOf(O.tanimlar.kohort_baslangic);   // 2017-01
  const SON_TAM = V.aylar.indexOf(O.tanimlar.son_tam_ay);      // 2018-07
  function kohortHesapla() {
    const boy = new Array(V.aylar.length).fill(0);
    const say = V.aylar.map(() => new Array(13).fill(0));
    for (let i = 0; i < N; i++) if (maske[i]) boy[M.ay[i]]++;
    for (const [k, offs] of Object.entries(M.tekrar_aylar)) {
      const i = +k; if (!maske[i]) continue;
      for (const o of offs) if (o >= 1 && o <= 12) say[M.ay[i]][o]++;
    }
    const satirlar = [];
    for (let a = Math.max(AY0, F.bas); a < SON_TAM && a <= F.bit; a++) {
      const hucre = [];
      for (let k = 1; k <= 12; k++) hucre.push(a + k > SON_TAM ? null : { n: say[a][k], p: boy[a] ? say[a][k] / boy[a] * 100 : null });
      satirlar.push({ a, boy: boy[a], hucre });
    }
    return satirlar;
  }
  function kohortCiz() {
    const sat = kohortHesapla();
    const kutu = $("#isi-harita"); kutu.innerHTML = "";
    const not = $("#kohort-not"); not.innerHTML = "";
    if (!sat.length) { kutu.append(el("p", { class: "kucuk" }, "Seçili ay aralığında 2017-01 ile 2018-06 arasında kohort yok.")); return; }
    let enb = 0; sat.forEach((s) => s.hucre.forEach((h) => { if (h && h.p != null) enb = Math.max(enb, h.p); }));
    enb = Math.max(enb, 0.2);
    const sol = 96, ust = 34, hw = 58, hh = 24, sag = 70;
    const W = sol + 12 * (hw + 3) + sag, H = ust + sat.length * (hh + 3) + 8;
    const svg = svgKok(W, H, "Kohort tutunma ısı haritası");
    for (let k = 1; k <= 12; k++) svg.append(metin(sol + (k - 1) * (hw + 3) + hw / 2, 20, k + ". ay", { "text-anchor": "middle" }));
    svg.append(metin(W - 4, 20, "kohort", { "text-anchor": "end" }));
    sat.forEach((s, r) => {
      const y = ust + r * (hh + 3);
      svg.append(metin(sol - 10, y + hh / 2 + 4, ayEtiket(V.aylar[s.a]), { "text-anchor": "end" }));
      svg.append(metin(W - 4, y + hh / 2 + 4, sayi(s.boy), { "text-anchor": "end" }));
      s.hucre.forEach((h, k) => {
        const x = sol + k * (hw + 3);
        if (!h) { svg.append(S("rect", { x, y, width: hw, height: hh, rx: 3, fill: "none", stroke: R.cizgi, "stroke-dasharray": "3 3" })); return; }
        const p = h.p || 0;
        const g = S("g", { "data-ipucu": `<b>${ayEtiket(V.aylar[s.a], true)}</b> kohortu, ${k + 1}. ay<br>${sayi(h.n)} / ${sayi(s.boy)} müşteri yeniden alışveriş yaptı<br><b>${yuzde(p, 2)}</b>` });
        g.append(S("rect", { x, y, width: hw, height: hh, rx: 3, fill: yesilOlcek(p / enb) }));
        if (p / enb > 0.55) g.append(metin(x + hw / 2, y + hh / 2 + 4, ondalik(p, 2), { "text-anchor": "middle", fill: "#fff", style: "fill:#fff;font-size:11.5px" }));
        svg.append(g);
      });
    });
    kutu.append(svg);
    // ağırlıklı ortalamalar
    const agir = (k) => { let a = 0, b = 0; sat.forEach((s) => { const h = s.hucre[k - 1]; if (h) { a += h.n; b += s.boy; } }); return b ? a / b * 100 : null; };
    const a1 = agir(1), a12 = agir(12);
    not.append(el("div", {}, el("p", { class: "sayi" }, a1 == null ? "–" : yuzde(a1, 2)), el("p", {}, "İlk alışverişten sonraki ay yeniden gelen müşteri payı (kohort büyüklüğüyle ağırlıklı ortalama).")));
    not.append(el("div", {}, el("p", { class: "sayi" }, a12 == null ? "–" : yuzde(a12, 2)), el("p", {}, "12. ayda yeniden gelenler. Tutunma ilk aydan sonra düşüyor ve %1’in altında kalıyor.")));
    const ol = el("div", { class: "olcek" }, el("div", { class: "olcek-bant", style: `background:linear-gradient(90deg, ${yesilOlcek(0)}, ${yesilOlcek(0.5)}, ${yesilOlcek(1)})` }),
      el("div", { class: "olcek-uclar" }, el("span", {}, "%0"), el("span", {}, yuzde(enb, 2))), el("span", {}, "Kesikli çerçeve: henüz gözlenmedi (son tam ay Temmuz 2018). Sağdaki sayı kohort büyüklüğü."));
    not.append(ol);
    if (filtreVar()) not.append(el("p", {}, "Küçük kohortlarda tek bir müşteri oranı belirgin biçimde değiştirir; hücre üzerine gelerek müşteri sayısına bakın."));
  }

  /* ---------------- 3. Geri dönüş zamanı ---------------- */
  const kaydir = $("#gun-kaydir");
  let araliklar = [];
  function donusHesapla() {
    araliklar = [];
    for (let i = 0; i < N; i++) if (maske[i] && M.ara_gun[i] >= 0) araliklar.push(M.ara_gun[i]);
    araliklar.sort((a, b) => a - b);
  }
  const ecdfPay = (g) => { let lo = 0, hi = araliklar.length; while (lo < hi) { const m = (lo + hi) >> 1; if (araliklar[m] <= g) lo = m + 1; else hi = m; } return araliklar.length ? lo / araliklar.length * 100 : 0; };
  function donusCiz() {
    const g = +kaydir.value;
    $("#gun-deger").textContent = sayi(g) + " gün";
    const n = araliklar.length;
    const kutu = $("#ecdf"); kutu.innerHTML = "";
    if (!n) { $("#gun-sonuc").textContent = "Seçimde ikinci kez alışveriş yapan müşteri yok."; return; }
    const p = ecdfPay(g);
    const medyan = araliklar[Math.floor((n - 1) / 2)];
    $("#gun-sonuc").innerHTML = `Geri dönen ${sayi(n)} müşterinin <mark>${yuzde(p)}${iyelik(ondalik(p))}</mark> ilk alışverişten sonraki ${sayi(g)} gün içinde döndü. Medyan ${sayi(medyan)} gün.`;
    const W = 1000, H = 330, sol = 50, alt = 34, ust = 12, sag = 16;
    const xm = 600, x = (d) => sol + Math.min(d, xm) / xm * (W - sol - sag), y = (q) => ust + (1 - q / 100) * (H - ust - alt);
    const svg = svgKok(W, H, `İkinci alışverişe kadar geçen sürenin birikimli dağılımı, ${n} müşteri`);
    [0, 25, 50, 75, 100].forEach((q) => { svg.append(S("line", { x1: sol, x2: W - sag, y1: y(q), y2: y(q), stroke: R.cizgi })); svg.append(metin(sol - 8, y(q) + 4, "%" + q, { "text-anchor": "end" })); });
    [0, 30, 90, 180, 270, 365, 450, 600].forEach((d) => svg.append(metin(x(d), H - 12, d, { "text-anchor": "middle" })));
    svg.append(metin(W - sag, H - 12 + 0, "", {}));
    let yol = `M${x(0)} ${y(0)}`;
    for (let d = 0; d <= xm; d += 2) yol += ` L${x(d).toFixed(1)} ${y(ecdfPay(d)).toFixed(1)}`;
    svg.append(S("path", { d: yol + ` L${x(xm)} ${y(0)} Z`, fill: R.mata, "fill-opacity": 0.08 }));
    svg.append(S("path", { d: yol, fill: "none", stroke: R.mata, "stroke-width": 3, "stroke-linejoin": "round" }));
    [180, 365].forEach((d) => { svg.append(S("line", { x1: x(d), x2: x(d), y1: ust, y2: H - alt, stroke: R.rosa, "stroke-dasharray": "4 5" })); svg.append(metin(x(d) + 6, H - alt - 40, d === 180 ? "180 gün: ana churn eşiği" : "365 gün: karşılaştırma", { style: `fill:${R.rosa}` })); });
    svg.append(S("line", { x1: x(g), x2: x(g), y1: y(p), y2: H - alt, stroke: R.tinta, "stroke-width": 1.5 }));
    svg.append(S("line", { x1: sol, x2: x(g), y1: y(p), y2: y(p), stroke: R.tinta, "stroke-width": 1.5, "stroke-dasharray": "2 4" }));
    svg.append(S("circle", { cx: x(g), cy: y(p), r: 8, fill: R.ipe, stroke: R.tinta, "stroke-width": 2 }));
    svg.append(metin(W - sag, H - alt - 8, "ilk alışverişten sonra geçen gün →", { "text-anchor": "end" }));
    // grafiğe tıklayınca kaydırıcıyı oraya taşı
    svg.addEventListener("click", (e) => { const r = svg.getBoundingClientRect(); const px = (e.clientX - r.left) / r.width * W; kaydir.value = Math.max(1, Math.min(600, Math.round((px - sol) / (W - sol - sag) * xm))); donusCiz(); });
    svg.style.cursor = "crosshair";
    kutu.append(svg);
  }
  kaydir.addEventListener("input", donusCiz);

  /* ---------------- 4. RFM ---------------- */
  (function puanTablo() {
    const t = $("#puan-tablo");
    t.append(el("tr", {}, el("th", {}, "Puan"), el("th", {}, "R: son alışverişten bu yana"), el("th", {}, "M: toplam harcama")));
    for (let p = 5; p >= 1; p--) t.append(el("tr", {}, el("td", {}, p), el("td", {}, R_ARALIK[p]), el("td", {}, M_ARALIK[p])));
  })();
  let seciliSeg = 2;
  const segIcin = (f, r, m) => f >= 2 ? (r >= 4 ? 0 : 1) : r >= 4 ? (m >= 4 ? 2 : 3) : r === 3 ? 4 : m >= 4 ? 5 : 6;
  function rfmHesapla() {
    const izg = {}; const seg = SEG.map(() => ({ n: 0, ciro: 0, son: 0 }));
    let top = 0, topCiro = 0;
    for (let i = 0; i < N; i++) if (maske[i]) {
      const s = M.segment[i], h = M.harcama_kurus[i] / 100;
      seg[s].n++; seg[s].ciro += h; seg[s].son += M.son_alim_gun[i]; top++; topCiro += h;
      if (M.gun[i] === 1) { const k = M.r[i] + "-" + M.m[i]; izg[k] = (izg[k] || 0) + 1; }
    }
    return { izg, seg, top, topCiro };
  }
  let rfmSon = null;
  function rfmCiz() {
    const d = rfmSon = rfmHesapla();
    // ızgara
    const kutu = $("#rfm-izgara"); kutu.innerHTML = "";
    const sol = 150, ust = 10, cw = 128, ch = 62, gap = 4;
    const W = sol + 5 * (cw + gap) + 4, H = ust + 5 * (ch + gap) + 66;
    const svg = svgKok(W, H, "Tek gün alışveriş yapan müşteriler, yakınlık ve harcama puanına göre");
    let enb = 1; Object.values(d.izg).forEach((v) => (enb = Math.max(enb, v)));
    for (let mm = 5; mm >= 1; mm--) {
      const y = ust + (5 - mm) * (ch + gap);
      svg.append(metin(sol - 12, y + ch / 2 - 2, "M " + mm, { "text-anchor": "end", class: "etiket-koyu" }));
      svg.append(metin(sol - 12, y + ch / 2 + 15, M_ARALIK[mm].replace(" veya daha az", " ve altı").replace("’dan fazla", " üstü"), { "text-anchor": "end", style: "font-size:11.5px" }));
      for (let r = 1; r <= 5; r++) {
        const x = sol + (r - 1) * (cw + gap);
        const s = segIcin(1, r, mm), n = d.izg[r + "-" + mm] || 0;
        const g = S("g", { class: "izgara-hucre" + (s === seciliSeg ? " secili" : ""), tabindex: 0, role: "button", "data-seg": s,
          "aria-label": `${SEG[s]}: R ${r}, M ${mm}, ${n} müşteri`,
          "data-ipucu": `<b>${SEG[s]}</b><br>R ${r} (${R_ARALIK[r]}) · M ${mm} (${M_ARALIK[mm]})<br>${sayi(n)} müşteri` });
        g.append(S("rect", { x, y, width: cw, height: ch, rx: 6, fill: SEG_RENK[s], "fill-opacity": n ? 0.35 + 0.65 * Math.sqrt(n / enb) : 0.12 }));
        g.append(metin(x + 10, y + 24, sayi(n), { style: `fill:${n / enb > 0.25 ? SEG_YAZI[s] : R.tinta};font-family:var(--baslik);font-size:19px;font-weight:700` }));
        g.append(metin(x + 10, y + 44, KISA[s], { style: `fill:${n / enb > 0.25 ? SEG_YAZI[s] : R.tinta};font-size:11.5px;opacity:.9` }));
        svg.append(g);
      }
    }
    const yAlt = ust + 5 * (ch + gap) + 6;
    for (let r = 1; r <= 5; r++) {
      const x = sol + (r - 1) * (cw + gap) + cw / 2;
      svg.append(metin(x, yAlt + 14, "R " + r, { "text-anchor": "middle", class: "etiket-koyu" }));
      svg.append(metin(x, yAlt + 31, R_ARALIK[r], { "text-anchor": "middle", style: "font-size:11.5px" }));
    }
    svg.append(metin(sol, yAlt + 54, "← daha eski", { style: "font-size:12px" }));
    svg.append(metin(W - 4, yAlt + 54, "daha yakın zamanda →", { "text-anchor": "end", style: "font-size:12px" }));
    svg.append(metin(8, ust + 12, "↑ daha çok", { style: "font-size:12px" }));
    svg.append(metin(8, ust + 5 * (ch + gap) - 6, "↓ daha az", { style: "font-size:12px" }));
    kutu.append(svg);
    kutu.querySelectorAll(".izgara-hucre").forEach((g) => {
      const sec = () => { seciliSeg = +g.dataset.seg; rfmCiz(); };
      g.addEventListener("click", sec);
      g.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); sec(); } });
    });
    // tekrar alanlar
    const tk = $("#rfm-tekrar"); tk.innerHTML = "";
    [0, 1].forEach((s) => {
      const b = el("button", { type: "button", class: "tekrar-hucre", style: `background:${SEG_RENK[s]};color:${SEG_YAZI[s]};border-color:${s === seciliSeg ? R.tinta : "transparent"}` },
        el("b", {}, sayi(d.seg[s].n) + " müşteri"), `${SEG[s]} · ${s === 0 ? "son alışveriş 180 gün içinde" : "son alışveriş 180 günden eski"}`);
      b.addEventListener("click", () => { seciliSeg = s; rfmCiz(); });
      tk.append(b);
    });
    segmentKart();
    segmentCubuk();
  }
  function segmentKart() {
    const d = rfmSon, s = seciliSeg, b = SEG_BILGI[s], x = d.seg[s];
    const k = $("#segment-kart"); k.innerHTML = "";
    k.append(el("div", { class: "renk", style: `background:${SEG_RENK[s]}` }));
    k.append(el("h3", {}, SEG[s]));
    k.append(el("p", { class: "kural" }, b.kural));
    k.append(el("p", { class: "tanim" }, b.tanim));
    const dl = el("dl");
    const k2 = (t, v) => dl.append(el("div", {}, el("dt", {}, t), el("dd", {}, v)));
    k2("Müşteri", sayi(x.n));
    k2("Müşteri payı", d.top ? yuzde(x.n / d.top * 100) : "–");
    k2("Ciro payı", d.topCiro ? yuzde(x.ciro / d.topCiro * 100) : "–");
    k2("Ortalama harcama", x.n ? sayi(x.ciro / x.n) + " R$" : "–");
    k2("Son alışverişten bu yana", x.n ? sayi(x.son / x.n) + " gün" : "–");
    k2("Eylem grubu", b.grup);
    k.append(dl);
    k.append(el("p", { class: "oneri", html: `<b>Ne yapılabilir?</b> ${b.oneri}` }));
    k.append(el("p", { class: "olcut" }, "Nasıl ölçülür: " + b.olcut + ". Maliyet verisi olmadığından getiri hesaplanmadı; öneri test edilecek bir hipotezdir."));
  }
  function segmentCubuk() {
    const d = rfmSon, kutu = $("#segment-cubuk"); kutu.innerHTML = "";
    const W = 1000, satH = 46, sol = 200, H = SEG.length * satH + 40;
    const svg = svgKok(W, H, "Segmentlerin müşteri ve ciro payı");
    const enb = Math.max(...d.seg.map((x) => Math.max(d.top ? x.n / d.top : 0, d.topCiro ? x.ciro / d.topCiro : 0))) * 100 || 1;
    const x = (p) => sol + p / enb * (W - sol - 90);
    svg.append(S("rect", { x: sol, y: 6, width: 14, height: 10, fill: R.filiz })); svg.append(metin(sol + 20, 15, "müşteri payı"));
    svg.append(S("rect", { x: sol + 130, y: 6, width: 14, height: 10, fill: R.mata })); svg.append(metin(sol + 150, 15, "ciro payı"));
    SEG.forEach((s, i) => {
      const y = 32 + i * satH, mp = d.top ? d.seg[i].n / d.top * 100 : 0, cp = d.topCiro ? d.seg[i].ciro / d.topCiro * 100 : 0;
      const g = S("g", { "data-ipucu": `<b>${s}</b><br>Müşterilerin ${yuzde(mp)}${iyelik(ondalik(mp))}<br>Cironun ${yuzde(cp)}${iyelik(ondalik(cp))}`, style: "cursor:pointer" });
      g.append(S("rect", { x: 0, y: y - 4, width: W, height: satH - 4, fill: i === seciliSeg ? "#E3EBE5" : "transparent", rx: 6 }));
      g.append(S("rect", { x: 12, y: y + 8, width: 12, height: 12, rx: 3, fill: SEG_RENK[i] }));
      g.append(metin(32, y + 19, s, { class: "etiket-koyu" }));
      g.append(S("rect", { x: sol, y: y, width: Math.max(1, x(mp) - sol), height: 13, rx: 3, fill: R.filiz }));
      g.append(S("rect", { x: sol, y: y + 16, width: Math.max(1, x(cp) - sol), height: 13, rx: 3, fill: R.mata }));
      g.append(metin(x(mp) + 6, y + 11, yuzde(mp)));
      g.append(metin(x(cp) + 6, y + 27, yuzde(cp), { class: "etiket-koyu" }));
      g.addEventListener("click", () => { seciliSeg = i; rfmCiz(); $("#segment-kart").scrollIntoView({ block: "nearest", behavior: "smooth" }); });
      svg.append(g);
    });
    kutu.append(svg);
  }

  /* ---------------- 5. Churn ---------------- */
  let esik = "180";
  const etkenler = [...new Set(V.churn["180"].etkenler.map((e) => e.faktor))];
  secenekler($("#etken"), etkenler.map((f) => [f, f]));
  $("#etken").value = "Teslimat süresi";
  $("#etken").addEventListener("change", churnCiz);
  document.querySelectorAll("#churn .segmentli button").forEach((b) => b.addEventListener("click", () => {
    esik = b.dataset.esik;
    document.querySelectorAll("#churn .segmentli button").forEach((x) => x.setAttribute("aria-checked", x === b));
    churnCiz();
  }));
  function churnCiz() {
    const o = O.churn[esik + "g"], c = V.churn[esik], md = o.model;
    const tes = c.testler.find((t) => t.karsilastirma.startsWith("Teslimat ≤7"));
    const ust = $("#churn-ust"); ust.innerHTML = "";
    const k = (b, s) => ust.append(el("div", {}, el("b", {}, b), el("span", {}, s)));
    k(sayi(o.populasyon.penceresi_kapanmis), `müşterinin ${esik} günlük süresi doldu`);
    k(yuzde(o["tekrar_alim_%"], 2), `${esik} gün içinde geri döndü (${sayi(o.populasyon.geri_donen)} kişi)`);
    k(`${yuzde(tes["oran_A_%"], 2)} / ${yuzde(tes["oran_B_%"], 2)}`, `geri dönüş: teslimat ≤7 gün / 21 günden uzun`);
    k(ondalik(md.auc_lojistik, 3).replace(/0+$/, ""), `model AUC (0,5 = rastgele tahmin)`);
    // etken grafiği
    const f = $("#etken").value, satir = c.etkenler.filter((e) => e.faktor === f);
    const kutu = $("#etken-grafik"); kutu.innerHTML = "";
    const W = 580, sol = 200, satH = 40, H = satir.length * satH + 46;
    const enb = Math.max(...satir.map((s) => s["ga_ust_%"])) * 1.08;
    const x = (p) => sol + p / enb * (W - sol - 70);
    const svg = svgKok(W, H, `${f}: ${esik} günde geri dönüş oranı`);
    const genel = o["tekrar_alim_%"];
    const adim = enb > 4 ? 1 : 0.5;
    for (let t = 0; t <= enb; t += adim) { svg.append(S("line", { x1: x(t), x2: x(t), y1: 6, y2: H - 30, stroke: R.cizgi })); svg.append(metin(x(t), H - 12, "%" + ondalik(t, adim < 1 ? 1 : 0), { "text-anchor": "middle" })); }
    satir.forEach((s, i) => {
      const y = 10 + i * satH, p = s["tekrar_alim_%"];
      const g = S("g", { "data-ipucu": `<b>${s.seviye}</b><br>${sayi(s.geri_donen)} / ${sayi(s.n)} müşteri geri döndü<br><b>${yuzde(p, 2)}</b> (aralık ${ondalik(s["ga_alt_%"], 2)}–${ondalik(s["ga_ust_%"], 2)})` });
      g.append(metin(sol - 12, y + 17, s.seviye, { "text-anchor": "end", class: "etiket-koyu" }));
      g.append(metin(sol - 12, y + 32, sayi(s.n) + " müşteri", { "text-anchor": "end", style: "font-size:11.5px" }));
      g.append(S("rect", { x: sol, y: y + 5, width: x(p) - sol, height: 20, rx: 3, fill: esik === "180" ? R.mata : R.rosa, "fill-opacity": 0.85 }));
      g.append(S("line", { x1: x(s["ga_alt_%"]), x2: x(s["ga_ust_%"]), y1: y + 15, y2: y + 15, stroke: R.tinta, "stroke-width": 2 }));
      [s["ga_alt_%"], s["ga_ust_%"]].forEach((v) => g.append(S("line", { x1: x(v), x2: x(v), y1: y + 9, y2: y + 21, stroke: R.tinta, "stroke-width": 2 })));
      g.append(metin(x(s["ga_ust_%"]) + 8, y + 20, ondalik(p, 2), { class: "etiket-koyu" }));
      svg.append(g);
    });
    svg.append(S("line", { x1: x(genel), x2: x(genel), y1: 4, y2: H - 30, stroke: R.ipe, "stroke-width": 3 }));
    svg.append(metin(x(genel) + 5, H - 30, "genel " + yuzde(genel, 2), { style: "fill:#8A6A00;font-weight:600" }));
    kutu.append(svg);
    // testler
    const tk = $("#testler"); tk.innerHTML = "";
    tk.append(el("p", { class: "kucuk", style: "margin:0 0 10px" }, "İki grubun geri dönüş oranı karşılaştırıldı (iki oran z testi). Beş karşılaştırma yapıldığı için p değerleri 5 ile çarpıldı (Bonferroni düzeltmesi). Düzeltilmiş p 0,05’ten küçükse farkın tesadüf olması düşük ihtimaldir; bu bir neden-sonuç kanıtı değildir."));
    c.testler.forEach((t) => {
      const [a, b] = t.karsilastirma.split(" vs ");
      tk.append(el("div", { class: "test" },
        el("span", { class: "ad" }, `${a} ile ${b}`),
        el("span", { class: "rozet " + (t.anlamli_0_05_duzeltilmis ? "evet" : "hayir") }, t.anlamli_0_05_duzeltilmis ? "Anlamlı fark" : "Belirsiz"),
        el("span", { class: "detay" }, `${yuzde(t["oran_A_%"], 2)} (${sayi(t.n_A)} kişi) ile ${yuzde(t["oran_B_%"], 2)} (${sayi(t.n_B)} kişi) · düzeltilmiş p = ${ondalik(Math.min(1, t.p_bonferroni), 3)}`)));
    });
    aucCiz(md); desilCiz(c.desil, md);
  }
  function aucCiz(md) {
    const kutu = $("#auc"); kutu.innerHTML = "";
    const W = 520, H = 230, sol = 150, sag = 20, a = 0.45, b = 0.65;
    const x = (v) => sol + (v - a) / (b - a) * (W - sol - sag);
    const svg = svgKok(W, H, "AUC karşılaştırması");
    svg.append(metin(0, 18, "Ayırt etme gücü (AUC), %95 aralık", { class: "etiket-koyu" }));
    [0.45, 0.5, 0.55, 0.6, 0.65].forEach((v) => { svg.append(S("line", { x1: x(v), x2: x(v), y1: 40, y2: H - 34, stroke: v === 0.5 ? R.tinta : R.cizgi, "stroke-dasharray": v === 0.5 ? "4 4" : null })); svg.append(metin(x(v), H - 16, ondalik(v, 2), { "text-anchor": "middle" })); });
    svg.append(metin(x(0.5) + 5, 52, "rastgele", { style: "font-size:12px" }));
    const satir = [["Lojistik model", md.auc_lojistik, md.auc_lojistik_ga, R.mata], ["Teslimat kuralı", md.auc_baslangic_teslimat_kurali, md.auc_baslangic_ga, R.rosa]];
    satir.forEach(([ad, v, ga, renk], i) => {
      const y = 92 + i * 56;
      const g = S("g", { "data-ipucu": `<b>${ad}</b><br>AUC ${ondalik(v, 3)} (aralık ${ondalik(ga[0], 3)}–${ondalik(ga[1], 3)})` });
      g.append(metin(sol - 12, y + 5, ad, { "text-anchor": "end", class: "etiket-koyu" }));
      g.append(S("line", { x1: x(ga[0]), x2: x(ga[1]), y1: y, y2: y, stroke: renk, "stroke-width": 6, "stroke-linecap": "round", "stroke-opacity": 0.45 }));
      g.append(S("circle", { cx: x(v), cy: y, r: 9, fill: renk, stroke: "#fff", "stroke-width": 2.5 }));
      g.append(metin(x(v), y - 15, ondalik(v, 3), { "text-anchor": "middle", class: "etiket-koyu" }));
      svg.append(g);
    });
    kutu.append(svg);
    kutu.append(el("p", { class: "kucuk" }, `Model zaman sırasına göre denendi: ${tarihKisa(md.egitim_bitis)} tarihine kadar teslim edilen ${sayi(md.egitim_n)} müşteriyle eğitildi, sonraki ${sayi(md.test_n)} müşteride sınandı. Kural: “teslimat ne kadar kısaysa geri dönüş o kadar olası”. Aralıklar örtüşüyor; model kuraldan belirgin biçimde iyi değil.`));
  }
  function desilCiz(desil, md) {
    const kutu = $("#desil"); kutu.innerHTML = "";
    const W = 520, H = 230, sol = 40, alt = 40, ust = 34;
    const enb = Math.max(1.6, ...desil.map((d) => d.lift));
    const bw = (W - sol - 10) / desil.length;
    const y = (v) => ust + (1 - v / enb) * (H - ust - alt);
    const svg = svgKok(W, H, "Model skor dilimlerine göre geri dönüş");
    svg.append(metin(0, 18, "Skor dilimine göre geri dönüş (ortalamanın katı)", { class: "etiket-koyu" }));
    desil.forEach((d, i) => {
      const xx = sol + i * bw;
      const g = S("g", { "data-ipucu": `<b>${d.desil}. dilim</b> (${d.desil === 1 ? "en yüksek skor" : d.desil === 10 ? "en düşük skor" : "skor sırası"})<br>${sayi(d.n)} müşteri, geri dönüş ${yuzde(d["tekrar_alim_%"], 2)}<br>ortalamanın ${ondalik(d.lift, 2)} katı` });
      g.append(S("rect", { x: xx + 4, y: y(d.lift), width: bw - 8, height: y(0) - y(d.lift), rx: 3, fill: i === 0 ? R.ipe : R.filiz }));
      g.append(metin(xx + bw / 2, H - alt + 18, d.desil, { "text-anchor": "middle" }));
      svg.append(g);
    });
    svg.append(S("line", { x1: sol, x2: W - 10, y1: y(1), y2: y(1), stroke: R.tinta, "stroke-dasharray": "4 4" }));
    svg.append(metin(W - 10, y(1) - 6, "ortalama = 1", { "text-anchor": "end", style: "font-size:12px" }));
    svg.append(metin(sol, H - 4, "← en yüksek skorlu %10", { style: "font-size:12px" }));
    kutu.append(svg);
    kutu.append(el("p", { class: "kucuk" }, `En yüksek skorlu %10’luk dilim, geri dönenlerin ${yuzde(md["ilk_desil_yakalama_%"])}${iyelik(ondalik(md["ilk_desil_yakalama_%"]))} yakalıyor; rastgele seçim %10 yakalardı. Hedeflemede küçük bir iyileşme.`));
  }

  /* ---------------- 6. Sepet ---------------- */
  function sepetCiz() {
    const y = O.sepet.yapi;
    const kutu = $("#sepet-yapi"); kutu.innerHTML = "";
    const W = 1000, H = 150;
    const svg = svgKok(W, H, "Siparişlerin ürün ve kategori yapısı");
    const parca = [["Tek ürün", y["tek_kalemli_%"], R.mata, y.ort_tutar_tek_kalem], ["Birden fazla ürün, tek kategori", y["cok_kalemli_tek_kategori_%"], R.yaprak, y.ort_tutar_cok_kalem], ["Birden fazla kategori", y["cok_kategorili_%"], R.ipe, y.ort_tutar_cok_kategori]];
    let x = 0;
    parca.forEach(([ad, p, renk, tutar], i) => {
      const w = p / 100 * W;
      svg.append(S("rect", { x, y: 40, width: Math.max(w, 6), height: 46, fill: renk, "data-ipucu": `<b>${ad}</b><br>Siparişlerin ${yuzde(p)}${iyelik(ondalik(p))}<br>Ortalama tutar ${sayi(tutar)} R$` }));
      x += w;
    });
    svg.append(metin(16, 70, `Tek ürün · ${yuzde(parca[0][1])}`, { style: "fill:#fff;font-size:17px;font-weight:600;font-family:var(--baslik)" }));
    svg.append(metin(W, 26, `Birden fazla ürün, tek kategori · ${yuzde(parca[1][1])}`, { "text-anchor": "end" }));
    svg.append(metin(W, 112, `Birden fazla kategori · ${yuzde(parca[2][1], 1)}`, { "text-anchor": "end", class: "etiket-koyu" }));
    svg.append(metin(0, 140, `Ortalama sipariş tutarı: tek ürün ${sayi(parca[0][3])} R$ · çok ürün ${sayi(parca[1][3])} R$ · çok kategori ${sayi(parca[2][3])} R$`, {}));
    kutu.append(svg);
    // çiftler
    const ck = $("#ciftler"); ck.innerHTML = "";
    ck.append(el("div", { class: "lejant" }, el("span", {}, el("i", { style: `background:${R.mata}` }), "30 veya daha fazla sipariş"), el("span", {}, el("i", { style: `background:repeating-linear-gradient(135deg, ${R.filiz} 0 4px, #DCE6DF 4px 8px)` }), "30’dan az: küçük örneklem, oranlar oynak")));
    const cf = V.sepet.ciftler, enb = Math.max(...cf.map((c) => c.birlikte_siparis));
    cf.forEach((c) => {
      const yon = c["guven_B_A_%"] > c["guven_A_B_%"] ? [c.kategori_B, c.kategori_A, c["guven_B_A_%"], c["guven_B_A_ga_alt_%"], c["guven_B_A_ga_ust_%"]] : [c.kategori_A, c.kategori_B, c["guven_A_B_%"], c["guven_A_B_ga_alt_%"], c["guven_A_B_ga_ust_%"]];
      const sat = el("div", { class: "cift" + (c.dusuk_orneklem ? " az" : ""),
        "data-ipucu": `<b>${c.kategori_A} + ${c.kategori_B}</b><br>${sayi(c.birlikte_siparis)} siparişte birlikte<br>${yon[0]} alanların ${yuzde(yon[2])}${iyelik(ondalik(yon[2]))} ${yon[1]} da aldı (aralık ${ondalik(yon[3])}–${ondalik(yon[4])})<br>Lift, çok kategorili siparişler içinde: ${ondalik(c.lift_cok_kategorili, 2)}` },
        el("span", { class: "ad" }, c.kategori_A, el("span", {}, " + "), c.kategori_B),
        el("div", {}, el("div", { class: "cubuk", style: `width:${c.birlikte_siparis / enb * 100}%` })),
        el("span", { class: "deger" }, `${sayi(c.birlikte_siparis)} sipariş · lift ${ondalik(c.lift_cok_kategorili, 2)}`));
      ck.append(sat);
    });
    ck.append(el("p", { class: "kucuk" }, "Lift: iki kategorinin birlikte alınma sıklığının, birbirinden bağımsız olsalardı beklenecek sıklığa oranı. 1’in üstü birlikte alınma eğilimi demektir. Burada yalnızca birden fazla kategori içeren siparişler içinde hesaplandı."));
    // çok ürünlü sipariş payı
    const kk = $("#cok-kalem"); kk.innerHTML = "";
    const liste = V.sepet.cok_kalem.slice().sort((a, b) => b["cok_kalemli_pay_%"] - a["cok_kalemli_pay_%"]);
    const W2 = 500, sol = 200, satH = 28, H2 = liste.length * satH + 12;
    const e2 = Math.max(...liste.map((l) => l["cok_kalemli_pay_%"]));
    const svg2 = svgKok(W2, H2, "Kategoriye göre birden fazla ürün içeren sipariş payı");
    liste.forEach((l, i) => {
      const yy = 6 + i * satH, w = l["cok_kalemli_pay_%"] / e2 * (W2 - sol - 60);
      const g = S("g", { "data-ipucu": `<b>${l.kategori}</b><br>${sayi(l.siparis)} sipariş, ortalama ${ondalik(l.ort_kalem, 2)} ürün<br>Birden fazla ürün içeren: ${yuzde(l["cok_kalemli_pay_%"])}` });
      g.append(metin(sol - 10, yy + 15, l.kategori, { "text-anchor": "end" }));
      g.append(S("rect", { x: sol, y: yy + 3, width: w, height: 16, rx: 3, fill: i < 3 ? R.mata : R.filiz }));
      g.append(metin(sol + w + 6, yy + 16, yuzde(l["cok_kalemli_pay_%"]), { class: i < 3 ? "etiket-koyu" : null }));
      svg2.append(g);
    });
    kk.append(svg2);
  }

  /* ---------------- 7. Tahmin ---------------- */
  let bf = "temiz";
  document.querySelectorAll("#tahmin .segmentli button").forEach((b) => b.addEventListener("click", () => {
    bf = b.dataset.bf;
    document.querySelectorAll("#tahmin .segmentli button").forEach((x) => x.setAttribute("aria-checked", x === b));
    tahminCiz();
  }));
  function tahminCiz() {
    const seri = V.tahmin.seri, ileri = V.tahmin.ileri, T = O.tahmin;
    const kutu = $("#seri"); kutu.innerHTML = "";
    const W = 820, H = 380, sol = 62, alt = 36, ust = 52, sag = 12;
    const n = seri.length + ileri.length;
    const deger = (s) => (bf === "temiz" ? s.ciro_temiz : s.ciro_ham);
    const enb = Math.max(...seri.map(deger), ...ileri.map((i) => i["ust_%90"]), ...ileri.map((i) => i.baslangic_tahmini)) * 1.06;
    const x = (i) => sol + i / (n - 1) * (W - sol - sag), y = (v) => ust + (1 - v / enb) * (H - ust - alt);
    const svg = svgKok(W, H, "Haftalık ciro ve 14 haftalık tahmin");
    for (let v = 0; v <= enb; v += 100000) { svg.append(S("line", { x1: sol, x2: W - sag, y1: y(v), y2: y(v), stroke: R.cizgi })); svg.append(metin(sol - 8, y(v) + 4, v ? bin(v) + " bin" : "0", { "text-anchor": "end" })); }
    const tum = seri.map((s) => s.hafta_baslangic).concat(ileri.map((s) => s.hafta_baslangic));
    tum.forEach((t, i) => { if (t.slice(8) <= "07" && ["01", "04", "07", "10"].includes(t.slice(5, 7))) svg.append(metin(x(i), H - 14, ayEtiket(t.slice(0, 7)), { "text-anchor": "middle" })); });
    const i0 = seri.length - 1;
    svg.append(S("rect", { x: x(i0), y: ust, width: W - sag - x(i0), height: H - ust - alt, fill: R.ipe, "fill-opacity": 0.09 }));
    svg.append(metin(x(i0) + 8, ust + 14, "tahmin", { style: "fill:#8A6A00;font-weight:600" }));
    // bant
    let bant = `M${x(i0)} ${y(deger(seri[i0]))}`;
    ileri.forEach((s, j) => (bant += ` L${x(i0 + 1 + j)} ${y(s["ust_%90"])}`));
    for (let j = ileri.length - 1; j >= 0; j--) bant += ` L${x(i0 + 1 + j)} ${y(ileri[j]["alt_%10"])}`;
    svg.append(S("path", { d: bant + " Z", fill: R.mata, "fill-opacity": 0.14 }));
    svg.append(S("path", { d: seri.map((s, i) => `${i ? "L" : "M"}${x(i).toFixed(1)} ${y(deger(s)).toFixed(1)}`).join(" "), fill: "none", stroke: R.tinta, "stroke-width": 2.2, "stroke-linejoin": "round" }));
    svg.append(S("path", { d: `M${x(i0)} ${y(deger(seri[i0]))} ` + ileri.map((s, j) => `L${x(i0 + 1 + j)} ${y(s.baslangic_tahmini)}`).join(" "), fill: "none", stroke: R.rosa, "stroke-width": 3, "stroke-dasharray": "2 6", "stroke-linecap": "round" }));
    svg.append(S("path", { d: `M${x(i0)} ${y(deger(seri[i0]))} ` + ileri.map((s, j) => `L${x(i0 + 1 + j)} ${y(s.tahmin_taban)}`).join(" "), fill: "none", stroke: R.mata, "stroke-width": 4 }));
    const bfI = seri.findIndex((s) => s.ciro_ham !== s.ciro_temiz);
    if (bfI >= 0) {
      const v = deger(seri[bfI]);
      svg.append(S("circle", { cx: x(bfI), cy: y(v), r: 6, fill: R.ipe, stroke: R.tinta, "stroke-width": 1.5 }));
      const ty = bf === "ham" ? y(v) + 4 : ust + 26;
      if (bf !== "ham") svg.append(S("line", { x1: x(bfI), x2: x(bfI), y1: ty + 6, y2: y(v) - 8, stroke: R.tinta, "stroke-dasharray": "2 3" }));
      svg.append(metin(x(bfI) + 10, ty, bf === "ham" ? `Black Friday 2017: ${bin(seri[bfI].ciro_ham)} bin R$` : `Black Friday 2017 arındırıldı (ham ${bin(seri[bfI].ciro_ham)} bin R$)`, { class: "etiket-koyu" }));
    }
    // hover için görünmez sütunlar
    tum.forEach((t, i) => {
      const s = i <= i0 ? seri[i] : ileri[i - i0 - 1];
      const ic = i <= i0 ? `<b>${tarihKisa(t)} haftası</b><br>Ciro: ${bin(deger(s))} bin R$` + (s.ciro_ham !== s.ciro_temiz ? `<br>Ham: ${bin(s.ciro_ham)} bin R$` : "")
        : `<b>${tarihKisa(t)} haftası (tahmin)</b><br>Model: ${bin(s.tahmin_taban)} bin R$<br>%80 aralık: ${bin(s["alt_%10"])}–${bin(s["ust_%90"])} bin<br>Başlangıç tahmini: ${bin(s.baslangic_tahmini)} bin`;
      svg.append(S("rect", { x: x(i) - (W - sol) / n / 2, y: ust, width: (W - sol) / n, height: H - ust - alt, fill: "transparent", "data-ipucu": ic }));
    });
    // lejant
    const lj = [[R.tinta, "Gerçekleşen", null, 2.2], [R.mata, "Model: log-doğrusal trend", null, 4], [R.rosa, "Başlangıç tahmini: son 4 hafta ortalaması", "2 6", 3]];
    let lx = sol;
    lj.forEach(([r, t, da, w]) => { svg.append(S("line", { x1: lx, x2: lx + 28, y1: 12, y2: 12, stroke: r, "stroke-width": w, "stroke-dasharray": da, "stroke-linecap": "round" })); svg.append(metin(lx + 34, 16, t)); lx += 46 + t.length * 7.1; });
    svg.append(S("rect", { x: sol, y: 26, width: 28, height: 12, fill: R.mata, "fill-opacity": 0.14 })); svg.append(metin(sol + 34, 36, "Modelin %80 aralığı (geçmiş test hatalarından)"));
    kutu.append(svg);
    const yan = $("#tahmin-yan"); yan.innerHTML = "";
    const tt = T.toplam, model = V.tahmin.test.find((m) => m.model === T.en_iyi_model), bas = V.tahmin.test.find((m) => m.baslangic_modeli);
    yan.append(el("div", { class: "blok yesil" }, el("span", {}, "14 haftalık toplam, model"), el("b", { html: milyon(tt.toplam_taban) + "<small> milyon R$</small>" }), el("span", {}, `%80 aralık ${milyon(tt["toplam_alt_%10"])}–${milyon(tt["toplam_ust_%90"])} milyon. Geçmiş testteki ortalama hata ${yuzde(model["WAPE_h1-14_%"])}.`)));
    yan.append(el("div", { class: "blok pembe" }, el("span", {}, "14 haftalık toplam, başlangıç tahmini"), el("b", { html: milyon(T.baslangic_modeli_toplam_taban) + "<small> milyon R$</small>" }), el("span", {}, `Son 4 haftanın ortalaması sabit tutuldu. Geçmiş testteki ortalama hata ${yuzde(bas["WAPE_h1-14_%"])}.`)));
    yan.append(el("div", { class: "blok" }, el("span", {}, "Fark neden büyük?"), el("p", { style: "font-size:15px;margin-top:4px" }, "Temmuz–Ağustos 2018 haftaları yüksekti. Başlangıç tahmini bu seviyeyi sürdürür; model son 26 haftanın daha yatay eğilimini izler. Black Friday 2018 iki tahmine de dahil değil.")));
    // test tablosu
    const tb = $("#test-tablo"); tb.innerHTML = "";
    const tab = el("table", { class: "tablo" });
    tab.append(el("tr", {}, ["Yöntem", "1–4 hafta sonrası hata", "5–14 hafta sonrası hata", "Ortalama hata (1–14 hafta)", "Yön (yanlılık)", "Başlangıç tahminine göre"].map((h) => el("th", {}, h))));
    V.tahmin.test.slice().sort((a, b) => a["WAPE_h1-14_%"] - b["WAPE_h1-14_%"]).forEach((m) => {
      const yon = m["yanlilik_h1-14_%"];
      tab.append(el("tr", { class: m.model === T.en_iyi_model ? "iyi" : null },
        el("td", {}, m.model + (m.baslangic_modeli ? " (başlangıç)" : "")),
        el("td", {}, yuzde(m["WAPE_h1-4_%"])), el("td", {}, yuzde(m["WAPE_h5-14_%"])), el("td", {}, yuzde(m["WAPE_h1-14_%"])),
        el("td", {}, `${yon > 0 ? "fazla" : "az"} tahmin, ${yuzde(Math.abs(yon))}`),
        el("td", {}, m.baslangic_modeli ? "–" : `${m.baslangica_gore_iyilesme_puan >= 0 ? "" : "−"}${ondalik(Math.abs(m.baslangica_gore_iyilesme_puan), 2)} puan ${m.baslangica_gore_iyilesme_puan >= 0 ? "daha iyi" : "daha kötü"}`)));
    });
    tb.append(el("div", { class: "tablo-kutu" }, tab));
    tb.append(el("p", { class: "kucuk" }, `Hata (WAPE): tahmin ile gerçekleşen arasındaki farkların toplamının, gerçekleşen ciro toplamına oranı. Her yöntem için ${sayi(model.test_sayisi)} haftalık tahmin sınandı. Yanlılık: ortalamada fazla mı az mı tahmin ettiği.`));
    const yt = T.yeterlilik;
    $("#yeterlilik").textContent = `Veri yeterli değil: ${yt.hafta_sayisi} hafta var, yıllık mevsimselliği (ör. her yıl tekrar eden Kasım artışı) tahmin etmek için en az ${yt.mevsimsellik_icin_gereken_hafta} hafta gerekir. Black Friday yalnızca bir kez gözlendi; 2018 için ${milyon(tt.toplam_olay_senaryosu)} milyon R$’lık “Black Friday tekrar ederse” senaryosu yalnızca bir varsayımdır.`;
  }

  /* ---------------- 8. Yöntem ---------------- */
  (function yontem() {
    const f = O.veri.filtre, ak = $("#filtre-akis");
    const kutu = el("div", { class: "akis" });
    const s = (n, t, c) => kutu.append(el("div", { class: "akis-satir " + (c || "") }, el("span", { class: "n" }, n), el("span", {}, t)));
    s(sayi(f.toplam_siparis), "ham sipariş");
    s("−" + sayi(f.iptal_ulasilamaz_olusturuldu), "iptal edilen, ulaşılamaz ya da yalnızca oluşturulmuş", "eksi");
    s("−" + sayi(f.kalemi_yok), "hiç ürünü olmayan", "eksi");
    s("−" + sayi(f.odemesi_yok), "ödeme kaydı olmayan", "eksi");
    s("−" + sayi(f.bitis_tarihinden_sonra), "31 Ağustos 2018’den sonra verilen", "eksi");
    s(sayi(f.gecerli_siparis), `geçerli sipariş, ${sayi(O.veri.musteri)} müşteri`, "toplam");
    ak.append(kutu);
    ak.append(el("p", { class: "kucuk" }, "Müşteri, Olist’in her siparişte değişmeyen müşteri kimliğiyle (customer_unique_id) tanımlandı. Aynı gün verilen siparişler tek alışveriş sayıldı. Günlük sipariş sayısı 22 Ağustos 2018’den sonra hızla düştüğü için veri o tarihte eksik kabul edildi; geri dönüş süreleri 21 Ağustos’ta kapatıldı."));
    const sn = $("#sinirlar");
    ["Maliyet, kâr marjı ve müşteri edinme maliyeti verisi yok; önerilerin getirisi hesaplanmadı.",
      "Churn bulguları ilişkidir, neden-sonuç değildir. Teslimat farkı 180 günde anlamlı, 365 günde değil.",
      `Churn modelinin ayırt etme gücü zayıf (AUC ${ondalik(O.churn["180g"].model.auc_lojistik, 2)}).`,
      `Sepet: yalnızca ${sayi(O.sepet.cok_kategorili_siparis_bilinen)} sipariş birden fazla kategori içeriyor; ${O.sepet.cift_sayisi} çiftin ${O.sepet.dusuk_orneklemli_cift}${iyelik(O.sepet.dusuk_orneklemli_cift)} küçük örneklem.`,
      `Tahmin: ${O.tahmin.yeterlilik.hafta_sayisi} haftalık seri mevsimsellik için kısa; Black Friday tek gözlem.`,
      "Sonuçlar Olist’e aittir; başka bir perakendeciye doğrudan taşınamaz."].forEach((t) => sn.append(el("li", {}, t)));
    const terimler = [
      ["Kohort", "Aynı ayda ilk alışverişini yapan müşteri grubu."],
      ["Tutunma", "Bir kohorttan, ilk alışverişten sonraki belirli bir ayda yeniden alışveriş yapanların payı."],
      ["RFM", "Yakınlık (Recency), sıklık (Frequency) ve harcama (Monetary) puanlarıyla müşteri gruplama yöntemi."],
      ["Churn (müşteri kaybı)", "İlk sipariş teslim edildikten sonra belirli bir süre (burada 180 ya da 365 gün) içinde yeniden alışveriş yapmamak."],
      ["Güven aralığı (%95)", "Gerçek oranın büyük olasılıkla içinde olduğu aralık. Küçük gruplarda geniştir. Burada Wilson yöntemiyle hesaplandı."],
      ["p değeri", "Gerçekte fark yokken bu büyüklükte bir farkı tesadüfen görme olasılığı. Küçükse farkın tesadüf olması zordur."],
      ["Bonferroni düzeltmesi", "Birden fazla karşılaştırma yapınca tesadüfi “anlamlı” sonuçları azaltmak için p değerlerini karşılaştırma sayısıyla çarpmak."],
      ["AUC", "Bir modelin, geri dönecek müşteriyi dönmeyecek olandan ayırma gücü. 0,5 yazı tura, 1 kusursuz."],
      ["Lojistik regresyon", "Geri dönme olasılığını müşteri özelliklerinden tahmin eden istatistiksel model."],
      ["Destek", "Bir kategori çiftini birlikte içeren siparişlerin tüm siparişlere oranı."],
      ["Güven (sepet)", "A kategorisini içeren siparişlerin kaçında B’nin de olduğu."],
      ["Lift", "Birlikte alınma sıklığının, bağımsızlık varsayımıyla beklenen sıklığa oranı; 1’in üstü birlikte alınma eğilimi."],
      ["Geriye dönük test", "Tahmin yöntemini geçmişte, yalnızca o güne kadarki veriyle çalıştırıp sonraki haftalarla karşılaştırmak."],
      ["WAPE", "Toplam mutlak tahmin hatasının, gerçekleşen toplam ciroya oranı."],
      ["Başlangıç tahmini", "Karşılaştırma için kullanılan en basit yöntem: son 4 haftanın ortalamasını sabit tutmak."],
    ];
    const sz = $("#sozluk");
    terimler.forEach(([t, d]) => sz.append(el("div", {}, el("dt", {}, t), el("dd", {}, d))));
  })();

  /* ---------------- gezinme: bulunulan bölüm ---------------- */
  const linkler = [...document.querySelectorAll(".duraklar a")];
  const gozlem = new IntersectionObserver((girdiler) => {
    girdiler.forEach((g) => { if (g.isIntersecting) linkler.forEach((a) => a.classList.toggle("aktif", a.dataset.bolum === g.target.id)); });
  }, { rootMargin: "-40% 0px -55% 0px" });
  document.querySelectorAll(".bolum").forEach((b) => gozlem.observe(b));

  /* ---------------- çiz ---------------- */
  function ciz() {
    const n = maskeHesapla();
    $("#secili").innerHTML = `<b>${sayi(n)}</b> / ${sayi(N)} müşteri`;
    $("#temizle").disabled = !filtreVar();
    girisCiz(n);
    kohortCiz();
    donusHesapla(); donusCiz();
    if (F.segment >= 0) seciliSeg = F.segment;
    rfmCiz();
  }
  ciz();
  churnCiz();
  sepetCiz();
  tahminCiz();
})();
