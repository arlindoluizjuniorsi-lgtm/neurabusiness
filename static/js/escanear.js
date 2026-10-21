// Escanear Documentos -- captura por câmera, recorte/endireitamento manual
// dos 4 cantos (malha de triângulos com transform afim, já que o Canvas 2D
// só tem transform afim nativo, não perspectiva de verdade) e montagem do
// PDF final no servidor. Compartilhado entre o fluxo interno (NeuraBusiness)
// e o público (self-signup) -- cada página que inclui esse arquivo define
// window.ESC_POST_URL antes de carregá-lo.

let escPaginas = [];      // [{canvas, pb}] -- canvas já recortado/endireitado
let escImgAtual = null;   // ImageBitmap/Image da foto crua sendo recortada
let escCantos = [];       // [{x,y}] em coordenadas de EXIBIÇÃO (não da imagem original)
let escEscala = 1;        // fator exibição -> imagem original
let escArrastando = -1;
let escOffX = 0, escOffY = 0; // posição do canvas de origem dentro do wrap (usado pela lupa)

document.getElementById('esc-input-foto').addEventListener('change', async function (e) {
  const file = e.target.files[0];
  if (!file) return;
  this.value = '';
  try {
    escImgAtual = await createImageBitmap(file, { imageOrientation: 'from-image' });
  } catch (err) {
    escImgAtual = await new Promise((resolve, reject) => {
      const img = new Image();
      img.onload = () => resolve(img);
      img.onerror = reject;
      img.src = URL.createObjectURL(file);
    });
  }
  escAbrirRecorte();
});

// Tenta localizar os 4 cantos do documento automaticamente (como o
// CamScanner faz), pra já sugerir o recorte certo em vez de uma margem fixa.
// Sem OpenCV: monta um mapa de gradiente (estilo Sobel simplificado), varre
// cada borda da foto de fora pra dentro procurando a 1ª transição forte de
// contraste, ajusta uma reta por mínimos quadrados em cada lado e cruza as
// retas pra achar os 4 cantos. Se não achar um resultado plausível (poucas
// amostras, área absurda, quadrilátero torto) retorna null e quem chamou
// cai pra margem fixa de sempre -- o ajuste manual continua disponível.
function escDetectarBordas(ctx, W, H) {
  try {
    if (W < 40 || H < 40) return null;
    const dados = ctx.getImageData(0, 0, W, H).data;
    const cinza = new Float32Array(W * H);
    for (let i = 0, p = 0; i < dados.length; i += 4, p++) {
      cinza[p] = 0.299 * dados[i] + 0.587 * dados[i + 1] + 0.114 * dados[i + 2];
    }
    const mag = new Float32Array(W * H);
    let soma = 0, soma2 = 0, cont = 0;
    for (let y = 1; y < H - 1; y++) {
      for (let x = 1; x < W - 1; x++) {
        const idx = y * W + x;
        const gx = cinza[idx + 1] - cinza[idx - 1];
        const gy = cinza[idx + W] - cinza[idx - W];
        const m = Math.sqrt(gx * gx + gy * gy);
        mag[idx] = m;
        soma += m; soma2 += m * m; cont++;
      }
    }
    const media = soma / cont;
    const limiar = media + Math.sqrt(Math.max(0, soma2 / cont - media * media)) * 1.4;

    const AMOSTRAS = 11, INICIO = 0.12, FIM = 0.88;
    const pontosTopo = [], pontosBase = [], pontosEsq = [], pontosDir = [];
    for (let k = 0; k < AMOSTRAS; k++) {
      const t = INICIO + (FIM - INICIO) * (k / (AMOSTRAS - 1));

      const x = Math.round(t * (W - 1));
      for (let y = Math.round(H * 0.03); y < Math.round(H * 0.62); y++) {
        if (mag[y * W + x] > limiar) { pontosTopo.push([x, y]); break; }
      }
      for (let y = Math.round(H * 0.97); y > Math.round(H * 0.38); y--) {
        if (mag[y * W + x] > limiar) { pontosBase.push([x, y]); break; }
      }

      const y2 = Math.round(t * (H - 1));
      for (let x2 = Math.round(W * 0.03); x2 < Math.round(W * 0.62); x2++) {
        if (mag[y2 * W + x2] > limiar) { pontosEsq.push([x2, y2]); break; }
      }
      for (let x2 = Math.round(W * 0.97); x2 > Math.round(W * 0.38); x2--) {
        if (mag[y2 * W + x2] > limiar) { pontosDir.push([x2, y2]); break; }
      }
    }

    if (pontosTopo.length < 6 || pontosBase.length < 6 || pontosEsq.length < 6 || pontosDir.length < 6) return null;

    function ajustarHorizontal(pts) { // y = m*x + b
      let sx = 0, sy = 0, sxy = 0, sxx = 0;
      pts.forEach(([x, y]) => { sx += x; sy += y; sxy += x * y; sxx += x * x; });
      const n = pts.length, den = n * sxx - sx * sx;
      if (Math.abs(den) < 1e-6) return null;
      const m = (n * sxy - sx * sy) / den;
      return { m, b: (sy - m * sx) / n };
    }
    function ajustarVertical(pts) { // x = m*y + b
      let sy = 0, sx = 0, syx = 0, syy = 0;
      pts.forEach(([x, y]) => { sy += y; sx += x; syx += y * x; syy += y * y; });
      const n = pts.length, den = n * syy - sy * sy;
      if (Math.abs(den) < 1e-6) return null;
      const m = (n * syx - sy * sx) / den;
      return { m, b: (sx - m * sy) / n };
    }

    const topo = ajustarHorizontal(pontosTopo), base = ajustarHorizontal(pontosBase);
    const esq = ajustarVertical(pontosEsq), dir = ajustarVertical(pontosDir);
    if (!topo || !base || !esq || !dir) return null;

    function cruzar(h, v) { // h: y=h.m*x+h.b -- v: x=v.m*y+v.b
      const den = 1 - h.m * v.m;
      if (Math.abs(den) < 1e-6) return null;
      const x = (v.m * h.b + v.b) / den;
      return [x, h.m * x + h.b];
    }
    const tl = cruzar(topo, esq), tr = cruzar(topo, dir);
    const bl = cruzar(base, esq), br = cruzar(base, dir);
    if (!tl || !tr || !bl || !br) return null;
    const pontos = [tl, tr, br, bl];
    if (pontos.some(([x, y]) => !Number.isFinite(x) || !Number.isFinite(y))) return null;

    const folgaX = W * 0.15, folgaY = H * 0.15; // reta extrapolada longe do quadro = provável ruído
    for (const [x, y] of pontos) {
      if (x < -folgaX || x > W + folgaX || y < -folgaY || y > H + folgaY) return null;
    }

    const clamp = ([x, y]) => [Math.max(0, Math.min(W, x)), Math.max(0, Math.min(H, y))];
    const [TL, TR, BR, BL] = pontos.map(clamp);

    if ((TR[0] - TL[0]) < W * 0.05 || (BR[0] - BL[0]) < W * 0.05) return null;
    if ((BL[1] - TL[1]) < H * 0.05 || (BR[1] - TR[1]) < H * 0.05) return null;
    const area = Math.abs(
      (TL[0] * TR[1] - TR[0] * TL[1]) + (TR[0] * BR[1] - BR[0] * TR[1]) +
      (BR[0] * BL[1] - BL[0] * BR[1]) + (BL[0] * TL[1] - TL[0] * BL[1])
    ) / 2;
    const areaTotal = W * H;
    if (area < areaTotal * 0.12 || area > areaTotal * 1.03) return null;

    return [{ x: TL[0], y: TL[1] }, { x: TR[0], y: TR[1] }, { x: BR[0], y: BR[1] }, { x: BL[0], y: BL[1] }];
  } catch (e) {
    return null;
  }
}

function escAbrirRecorte() {
  const overlay = document.getElementById('esc-overlay');
  const wrap = document.getElementById('esc-canvas-wrap');
  overlay.style.display = 'block';

  const larguraTela = wrap.clientWidth;
  const alturaTela = wrap.clientHeight;
  const iw = escImgAtual.width, ih = escImgAtual.height;
  escEscala = Math.min(larguraTela / iw, alturaTela / ih);
  const dw = iw * escEscala, dh = ih * escEscala;

  const canvas = document.getElementById('esc-canvas-origem');
  canvas.width = dw; canvas.height = dh;
  canvas.style.position = 'absolute';
  canvas.style.left = ((larguraTela - dw) / 2) + 'px';
  canvas.style.top = ((alturaTela - dh) / 2) + 'px';
  const ctx = canvas.getContext('2d');
  ctx.drawImage(escImgAtual, 0, 0, dw, dh);

  const svg = document.getElementById('esc-svg-cantos');
  svg.setAttribute('width', larguraTela);
  svg.setAttribute('height', alturaTela);
  const ox = (larguraTela - dw) / 2, oy = (alturaTela - dh) / 2;
  escOffX = ox; escOffY = oy;

  const detectado = escDetectarBordas(ctx, canvas.width, canvas.height);
  if (detectado) {
    escCantos = detectado.map(p => ({ x: ox + p.x, y: oy + p.y }));
  } else {
    const m = 0.06; // margem inicial sugerida (fallback), 6% pra dentro de cada borda
    escCantos = [
      { x: ox + dw * m, y: oy + dh * m },             // TL
      { x: ox + dw * (1 - m), y: oy + dh * m },        // TR
      { x: ox + dw * (1 - m), y: oy + dh * (1 - m) },  // BR
      { x: ox + dw * m, y: oy + dh * (1 - m) },        // BL
    ];
  }
  escDesenharCantos();
}

function escDesenharCantos() {
  const svg = document.getElementById('esc-svg-cantos');
  svg.innerHTML = '';
  const ns = 'http://www.w3.org/2000/svg';
  const pts = escCantos.map(p => `${p.x},${p.y}`).join(' ');
  const poly = document.createElementNS(ns, 'polygon');
  poly.setAttribute('points', pts);
  poly.setAttribute('fill', 'rgba(249,115,22,0.18)');
  poly.setAttribute('stroke', '#f97316');
  poly.setAttribute('stroke-width', '2');
  svg.appendChild(poly);
  escCantos.forEach((p, i) => {
    const c = document.createElementNS(ns, 'circle');
    c.setAttribute('cx', p.x); c.setAttribute('cy', p.y); c.setAttribute('r', 16);
    c.setAttribute('fill', '#f97316'); c.setAttribute('stroke', '#fff'); c.setAttribute('stroke-width', '3');
    c.style.cursor = 'grab';
    c.addEventListener('pointerdown', (ev) => {
      escArrastando = i;
      ev.target.setPointerCapture(ev.pointerId);
      escAtualizarLupa(p.x, p.y);
    });
    svg.appendChild(c);
  });
}

document.getElementById('esc-svg-cantos').addEventListener('pointermove', (ev) => {
  if (escArrastando < 0) return;
  const rect = ev.currentTarget.getBoundingClientRect();
  const x = ev.clientX - rect.left, y = ev.clientY - rect.top;
  escCantos[escArrastando] = { x, y };
  escDesenharCantos();
  escAtualizarLupa(x, y);
});
['pointerup', 'pointercancel'].forEach(evt =>
  document.getElementById('esc-svg-cantos').addEventListener(evt, () => {
    escArrastando = -1;
    escEsconderLupa();
  })
);

// Lupa de precisão: mostra um recorte ampliado (2,8x) da imagem ORIGINAL
// (não da versão reduzida da tela, pra ficar nítida) em volta do ponto que
// está sendo arrastado, deslocada pra cima do dedo -- senão o próprio dedo
// cobre o canto e fica impossível ver se o ajuste ficou exato.
function escAtualizarLupa(dispX, dispY) {
  const lupa = document.getElementById('esc-lupa');
  const wrap = document.getElementById('esc-canvas-wrap');
  if (!lupa || !wrap || !escImgAtual) return;
  const TAM = lupa.width, ZOOM = 2.8;
  const raioFonte = (TAM / ZOOM) / 2;
  const imgX = (dispX - escOffX) / escEscala;
  const imgY = (dispY - escOffY) / escEscala;

  const ctx = lupa.getContext('2d');
  ctx.save();
  ctx.clearRect(0, 0, TAM, TAM);
  ctx.beginPath();
  ctx.arc(TAM / 2, TAM / 2, TAM / 2 - 2, 0, Math.PI * 2);
  ctx.closePath();
  ctx.clip();
  ctx.fillStyle = '#000';
  ctx.fillRect(0, 0, TAM, TAM);
  ctx.drawImage(escImgAtual, imgX - raioFonte, imgY - raioFonte, raioFonte * 2, raioFonte * 2, 0, 0, TAM, TAM);
  ctx.strokeStyle = 'rgba(249,115,22,0.9)';
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  ctx.moveTo(TAM / 2 - 10, TAM / 2); ctx.lineTo(TAM / 2 + 10, TAM / 2);
  ctx.moveTo(TAM / 2, TAM / 2 - 10); ctx.lineTo(TAM / 2, TAM / 2 + 10);
  ctx.stroke();
  ctx.restore();

  const larguraTela = wrap.clientWidth;
  let left = Math.max(4, Math.min(larguraTela - TAM - 4, dispX - TAM / 2));
  const GAP = 36;
  let top = dispY - GAP - TAM;
  if (top < 4) top = dispY + GAP;
  lupa.style.left = left + 'px';
  lupa.style.top = top + 'px';
  lupa.style.display = 'block';
}
function escEsconderLupa() {
  const lupa = document.getElementById('esc-lupa');
  if (lupa) lupa.style.display = 'none';
}

function escCancelarRecorte() {
  document.getElementById('esc-overlay').style.display = 'none';
  escImgAtual = null;
  escEsconderLupa();
}

// Resolve o sistema 2x3 que leva 3 pontos de origem em 3 pontos de destino --
// é o que permite desenhar cada pequeno triângulo da malha já "esticado"
// pro lugar certo (canvas 2D só tem transform afim, não perspectiva de
// verdade -- por isso a imagem é cortada numa malha fina de triângulos e
// cada um é desenhado com sua própria transformação afim).
function escResolverAfim(s0, s1, s2, d0, d1, d2) {
  const [x0, y0] = s0, [x1, y1] = s1, [x2, y2] = s2;
  const det = x0 * (y1 - y2) - y0 * (x1 - x2) + (x1 * y2 - x2 * y1);
  if (Math.abs(det) < 1e-9) return null;
  function resolverEixo(X0, X1, X2) {
    const a = (X0 * (y1 - y2) - y0 * (X1 - X2) + (X1 * y2 - X2 * y1)) / det;
    const c = (x0 * (X1 - X2) - X0 * (x1 - x2) + (x1 * X2 - x2 * X1)) / det;
    const e = (x0 * (y1 * X2 - y2 * X1) - y0 * (x1 * X2 - x2 * X1) + (x1 * y2 - x2 * y1) * X0) / det;
    return [a, c, e];
  }
  const [a, c, e] = resolverEixo(d0[0], d1[0], d2[0]);
  const [b, d, f] = resolverEixo(d0[1], d1[1], d2[1]);
  return [a, b, c, d, e, f];
}

function escBilinear(p0, p1, p2, p3, u, v) {
  // p0=TL p1=TR p2=BR p3=BL
  return [
    (1 - u) * (1 - v) * p0[0] + u * (1 - v) * p1[0] + u * v * p2[0] + (1 - u) * v * p3[0],
    (1 - u) * (1 - v) * p0[1] + u * (1 - v) * p1[1] + u * v * p2[1] + (1 - u) * v * p3[1],
  ];
}

function escWarp(imagemOrigem, cantosOrigemPx, larguraSaida, alturaSaida) {
  const canvasOut = document.createElement('canvas');
  canvasOut.width = larguraSaida; canvasOut.height = alturaSaida;
  const ctx = canvasOut.getContext('2d');
  const N = 24;
  const [s0, s1, s2, s3] = cantosOrigemPx; // TL TR BR BL, em pixels da imagem ORIGINAL
  for (let j = 0; j < N; j++) {
    for (let i = 0; i < N; i++) {
      const u0 = i / N, u1 = (i + 1) / N, v0 = j / N, v1 = (j + 1) / N;
      const dTl = [u0 * larguraSaida, v0 * alturaSaida];
      const dTr = [u1 * larguraSaida, v0 * alturaSaida];
      const dBr = [u1 * larguraSaida, v1 * alturaSaida];
      const dBl = [u0 * larguraSaida, v1 * alturaSaida];
      const sTl = escBilinear(s0, s1, s2, s3, u0, v0);
      const sTr = escBilinear(s0, s1, s2, s3, u1, v0);
      const sBr = escBilinear(s0, s1, s2, s3, u1, v1);
      const sBl = escBilinear(s0, s1, s2, s3, u0, v1);
      escDesenharTriangulo(ctx, imagemOrigem, sTl, sTr, sBr, dTl, dTr, dBr);
      escDesenharTriangulo(ctx, imagemOrigem, sTl, sBr, sBl, dTl, dBr, dBl);
    }
  }
  return canvasOut;
}

function escDesenharTriangulo(ctx, img, s0, s1, s2, d0, d1, d2) {
  const m = escResolverAfim(s0, s1, s2, d0, d1, d2);
  if (!m) return;
  // O recorte (clip) de cada triângulo é desenhado um pouquinho MAIOR que o
  // triângulo real (esticado a partir do centro) só pra servir de máscara --
  // a transformação em si usa os pontos originais, sem essa dilatação. Sem
  // isso, o anti-aliasing da borda de cada triângulo deixa uma linha fina
  // sem pintar entre um triângulo e o vizinho, e com 24x24 = 576 triângulos
  // isso aparece como listras/riscos na imagem final.
  const cx = (d0[0] + d1[0] + d2[0]) / 3, cy = (d0[1] + d1[1] + d2[1]) / 3;
  const dilatar = (p) => [cx + (p[0] - cx) * 1.03, cy + (p[1] - cy) * 1.03];
  const D0 = dilatar(d0), D1 = dilatar(d1), D2 = dilatar(d2);
  ctx.save();
  ctx.beginPath();
  ctx.moveTo(D0[0], D0[1]); ctx.lineTo(D1[0], D1[1]); ctx.lineTo(D2[0], D2[1]);
  ctx.closePath();
  ctx.clip();
  ctx.transform(m[0], m[1], m[2], m[3], m[4], m[5]);
  ctx.drawImage(img, 0, 0);
  ctx.restore();
}

function escConfirmarRecorte() {
  // cantos da tela (exibição) -> pixels da imagem original
  const wrap = document.getElementById('esc-canvas-wrap');
  const canvas = document.getElementById('esc-canvas-origem');
  const canvasRect = canvas.getBoundingClientRect();
  const wrapRect = wrap.getBoundingClientRect();
  const offX = canvasRect.left - wrapRect.left, offY = canvasRect.top - wrapRect.top;
  const cantosImg = escCantos.map(p => [(p.x - offX) / escEscala, (p.y - offY) / escEscala]);

  function sub(a, b) { return [a[0] - b[0], a[1] - b[1]]; }
  const largMedia = (Math.hypot(...sub(cantosImg[1], cantosImg[0])) + Math.hypot(...sub(cantosImg[2], cantosImg[3]))) / 2;
  const altMedia = (Math.hypot(...sub(cantosImg[3], cantosImg[0])) + Math.hypot(...sub(cantosImg[2], cantosImg[1]))) / 2;

  const MAX_LADO = 1600;
  let larguraSaida = largMedia, alturaSaida = altMedia;
  const maior = Math.max(larguraSaida, alturaSaida);
  if (maior > MAX_LADO) {
    const fator = MAX_LADO / maior;
    larguraSaida *= fator; alturaSaida *= fator;
  }
  larguraSaida = Math.max(50, Math.round(larguraSaida));
  alturaSaida = Math.max(50, Math.round(alturaSaida));

  const canvasFinal = escWarp(escImgAtual, cantosImg, larguraSaida, alturaSaida);
  escPaginas.push({ canvas: canvasFinal, pb: false });
  document.getElementById('esc-overlay').style.display = 'none';
  escImgAtual = null;
  escEsconderLupa();
  escRenderPaginas();
}

function escAplicarPB(canvasOrigem) {
  const c = document.createElement('canvas');
  c.width = canvasOrigem.width; c.height = canvasOrigem.height;
  const ctx = c.getContext('2d');
  ctx.drawImage(canvasOrigem, 0, 0);
  const img = ctx.getImageData(0, 0, c.width, c.height);
  const d = img.data;
  for (let i = 0; i < d.length; i += 4) {
    let g = 0.299 * d[i] + 0.587 * d[i + 1] + 0.114 * d[i + 2];
    g = Math.min(255, Math.max(0, (g - 128) * 1.35 + 128)); // contraste leve
    d[i] = d[i + 1] = d[i + 2] = g;
  }
  ctx.putImageData(img, 0, 0);
  return c;
}

function escRenderPaginas() {
  const cont = document.getElementById('esc-paginas');
  cont.innerHTML = '';
  escPaginas.forEach((pg, idx) => {
    const exibicao = pg.pb ? escAplicarPB(pg.canvas) : pg.canvas;
    const col = document.createElement('div');
    col.className = 'col-6 col-md-3 col-lg-2';
    col.innerHTML = `
      <div class="card h-100">
        <div class="card-body p-2 text-center">
          <img src="${exibicao.toDataURL('image/jpeg', 0.7)}" class="img-fluid rounded mb-1" style="max-height:160px; object-fit:contain;">
          <div class="small text-muted">Página ${idx + 1}</div>
          <div class="btn-group btn-group-sm w-100 mt-1">
            <button type="button" class="btn btn-outline-secondary" onclick="escTogglePB(${idx})">${pg.pb ? 'Cor' : 'P&B'}</button>
            <button type="button" class="btn btn-outline-danger" onclick="escRemoverPagina(${idx})"><i class="fas fa-trash"></i></button>
          </div>
        </div>
      </div>`;
    cont.appendChild(col);
  });
  document.getElementById('esc-contador').textContent = escPaginas.length;
  document.getElementById('esc-card-salvar').style.display = escPaginas.length ? 'block' : 'none';
}

function escTogglePB(idx) { escPaginas[idx].pb = !escPaginas[idx].pb; escRenderPaginas(); }
function escRemoverPagina(idx) { escPaginas.splice(idx, 1); escRenderPaginas(); }

function escCanvasParaBlob(canvas) {
  return new Promise(resolve => canvas.toBlob(resolve, 'image/jpeg', 0.85));
}

// Abre o menu nativo de compartilhamento do celular (Web Share API) com o
// PDF já baixado como arquivo -- cai pra só abrir o PDF numa aba nova se o
// navegador não suportar compartilhar arquivo (ex: desktop mais antigo).
async function escCompartilharArquivo(url, nomeArquivo) {
  try {
    const resp = await fetch(url);
    const blob = await resp.blob();
    const file = new File([blob], nomeArquivo || 'documento.pdf', { type: 'application/pdf' });
    if (navigator.canShare && navigator.canShare({ files: [file] })) {
      await navigator.share({ files: [file], title: nomeArquivo || 'Documento' });
      return;
    }
  } catch (e) {
    if (e && e.name === 'AbortError') return; // usuário cancelou o compartilhamento
  }
  window.open(url, '_blank');
}

let escUltimoGerado = null;
function escCompartilharGerado() {
  if (escUltimoGerado) escCompartilharArquivo(escUltimoGerado.url, escUltimoGerado.nome);
}

// Manda o PDF que acabou de ser gerado direto pro módulo de Assinatura de
// Documentos -- window.ESC_ASSINAR_URL_BASE e window.ESC_CSRF_TOKEN só são
// definidos nas páginas que têm esse botão (interna e pública, cada uma
// com sua própria base de rota).
function escAssinarGerado() {
  if (!escUltimoGerado || !escUltimoGerado.docId || !window.ESC_ASSINAR_URL_BASE) return;
  const form = document.createElement('form');
  form.method = 'POST';
  form.action = `${window.ESC_ASSINAR_URL_BASE}/${escUltimoGerado.docId}/assinar`;
  const input = document.createElement('input');
  input.type = 'hidden'; input.name = 'csrf_token'; input.value = window.ESC_CSRF_TOKEN || '';
  form.appendChild(input);
  document.body.appendChild(form);
  form.submit();
}

async function escGerarPdf() {
  if (!escPaginas.length) return;
  const status = document.getElementById('esc-status');
  const btn = document.getElementById('esc-btn-gerar');
  btn.disabled = true;
  status.textContent = 'Gerando PDF...';
  try {
    const fd = new FormData();
    fd.append('pasta', document.getElementById('esc-pasta').value || 'Geral');
    fd.append('nome', document.getElementById('esc-nome').value || '');
    for (const pg of escPaginas) {
      const canvasFinal = pg.pb ? escAplicarPB(pg.canvas) : pg.canvas;
      const blob = await escCanvasParaBlob(canvasFinal);
      fd.append('paginas', blob, 'pagina.jpg');
    }
    const resp = await fetch(window.ESC_POST_URL, { method: 'POST', body: fd });
    const data = await resp.json();
    if (data.ok) {
      status.textContent = '';
      btn.disabled = false;
      escUltimoGerado = { url: data.arquivo_url, nome: data.nome_arquivo, docId: data.doc_id };
      document.getElementById('esc-card-salvar').style.display = 'none';
      document.getElementById('esc-paginas').style.display = 'none';
      const linkPasta = document.getElementById('esc-link-pasta');
      if (linkPasta) linkPasta.href = data.redirect;
      const sucesso = document.getElementById('esc-card-sucesso');
      if (sucesso) sucesso.style.display = 'block';
    } else {
      status.textContent = 'Erro: ' + (data.erro || 'falha ao salvar');
      btn.disabled = false;
    }
  } catch (e) {
    status.textContent = 'Erro de conexão.';
    btn.disabled = false;
  }
}
