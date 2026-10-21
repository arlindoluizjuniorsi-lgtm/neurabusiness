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
  const m = 0.06; // margem inicial sugerida, 6% pra dentro de cada borda
  escCantos = [
    { x: ox + dw * m, y: oy + dh * m },             // TL
    { x: ox + dw * (1 - m), y: oy + dh * m },        // TR
    { x: ox + dw * (1 - m), y: oy + dh * (1 - m) },  // BR
    { x: ox + dw * m, y: oy + dh * (1 - m) },        // BL
  ];
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
    c.addEventListener('pointerdown', (ev) => { escArrastando = i; ev.target.setPointerCapture(ev.pointerId); });
    svg.appendChild(c);
  });
}

document.getElementById('esc-svg-cantos').addEventListener('pointermove', (ev) => {
  if (escArrastando < 0) return;
  const rect = ev.currentTarget.getBoundingClientRect();
  escCantos[escArrastando] = { x: ev.clientX - rect.left, y: ev.clientY - rect.top };
  escDesenharCantos();
});
['pointerup', 'pointercancel'].forEach(evt =>
  document.getElementById('esc-svg-cantos').addEventListener(evt, () => { escArrastando = -1; })
);

function escCancelarRecorte() {
  document.getElementById('esc-overlay').style.display = 'none';
  escImgAtual = null;
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
  ctx.save();
  ctx.beginPath();
  ctx.moveTo(d0[0], d0[1]); ctx.lineTo(d1[0], d1[1]); ctx.lineTo(d2[0], d2[1]);
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
      status.textContent = 'Salvo!';
      window.location.href = data.redirect;
    } else {
      status.textContent = 'Erro: ' + (data.erro || 'falha ao salvar');
      btn.disabled = false;
    }
  } catch (e) {
    status.textContent = 'Erro de conexão.';
    btn.disabled = false;
  }
}
