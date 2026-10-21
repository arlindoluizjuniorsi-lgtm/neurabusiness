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
// Sem OpenCV: reduz a foto pra uma grade pequena (isso também "borra" texto
// e ruído do papel, deixando só o contorno grande), estima a cor do fundo
// pela moldura da própria foto e marca como "documento" todo pixel que se
// afasta bastante dessa cor. Os 4 cantos (mesmo com a foto em ângulo) são
// os pontos extremos de x+y e x-y dentro dessa máscara -- jeito clássico de
// achar os cantos de um quadrilátero rotacionado sem contorno de verdade.
// Se o resultado não for plausível (fundo sem contraste, documento colado
// na borda, área implausível) retorna null e quem chamou cai pra margem
// fixa de sempre -- o ajuste manual continua disponível sempre.
function escDetectarBordas(ctx, W, H) {
  try {
    if (W < 40 || H < 40) return null;
    const GW = Math.min(140, W);
    const GH = Math.max(1, Math.round(GW * H / W));
    const off = document.createElement('canvas');
    off.width = GW; off.height = GH;
    const octx = off.getContext('2d');
    octx.drawImage(ctx.canvas, 0, 0, GW, GH);
    const dados = octx.getImageData(0, 0, GW, GH).data;

    const faixa = Math.max(1, Math.round(Math.min(GW, GH) * 0.035));
    let rs = 0, gs = 0, bs = 0, cont = 0;
    function amostrar(x, y) {
      const i = (y * GW + x) * 4;
      rs += dados[i]; gs += dados[i + 1]; bs += dados[i + 2]; cont++;
    }
    for (let x = 0; x < GW; x++) { amostrar(x, faixa); amostrar(x, GH - 1 - faixa); }
    for (let y = 0; y < GH; y++) { amostrar(faixa, y); amostrar(GW - 1 - faixa, y); }
    const fundoR = rs / cont, fundoG = gs / cont, fundoB = bs / cont;

    const dist = new Float32Array(GW * GH);
    let somaDist = 0, maxDist = 0;
    for (let p = 0, i = 0; p < GW * GH; p++, i += 4) {
      const dr = dados[i] - fundoR, dg = dados[i + 1] - fundoG, db = dados[i + 2] - fundoB;
      const d = Math.sqrt(dr * dr + dg * dg + db * db);
      dist[p] = d;
      somaDist += d;
      if (d > maxDist) maxDist = d;
    }
    if (maxDist < 35) return null; // sem contraste suficiente com o fundo pra confiar
    const mediaDist = somaDist / (GW * GH);
    const limiar = mediaDist + (maxDist - mediaDist) * 0.3;

    let minSoma = Infinity, maxSoma = -Infinity, minDif = Infinity, maxDif = -Infinity;
    let pTL = null, pTR = null, pBR = null, pBL = null, achou = 0;
    for (let y = 0; y < GH; y++) {
      for (let x = 0; x < GW; x++) {
        if (dist[y * GW + x] < limiar) continue;
        achou++;
        const soma = x + y, dif = x - y;
        if (soma < minSoma) { minSoma = soma; pTL = [x, y]; }
        if (soma > maxSoma) { maxSoma = soma; pBR = [x, y]; }
        if (dif > maxDif) { maxDif = dif; pTR = [x, y]; }
        if (dif < minDif) { minDif = dif; pBL = [x, y]; }
      }
    }
    if (!pTL || !pTR || !pBR || !pBL) return null;
    if (achou < GW * GH * 0.06) return null; // documento ocupa área irrelevante -- não confia

    const fatorX = W / GW, fatorY = H / GH;
    const [TL, TR, BR, BL] = [pTL, pTR, pBR, pBL].map(([x, y]) => [(x + 0.5) * fatorX, (y + 0.5) * fatorY]);

    function dist2(a, b) { return Math.hypot(a[0] - b[0], a[1] - b[1]); }
    const ladoMin = Math.min(dist2(TL, TR), dist2(TR, BR), dist2(BR, BL), dist2(BL, TL));
    if (ladoMin < Math.min(W, H) * 0.12) return null; // quadrilátero degenerado

    const area = Math.abs(
      (TL[0] * TR[1] - TR[0] * TL[1]) + (TR[0] * BR[1] - BR[0] * TR[1]) +
      (BR[0] * BL[1] - BL[0] * BR[1]) + (BL[0] * TL[1] - TL[0] * BL[1])
    ) / 2;
    const areaTotal = W * H;
    if (area < areaTotal * 0.1 || area > areaTotal * 1.02) return null;

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
  if (!lupa || !wrap) return;
  const TAM = lupa.width || 150, ZOOM = 2.8;
  try {
    if (escImgAtual) {
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
      ctx.fillStyle = '#1a1a1a';
      ctx.fillRect(0, 0, TAM, TAM);
      ctx.drawImage(escImgAtual, imgX - raioFonte, imgY - raioFonte, raioFonte * 2, raioFonte * 2, 0, 0, TAM, TAM);
      ctx.strokeStyle = 'rgba(249,115,22,0.95)';
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(TAM / 2 - 12, TAM / 2); ctx.lineTo(TAM / 2 + 12, TAM / 2);
      ctx.moveTo(TAM / 2, TAM / 2 - 12); ctx.lineTo(TAM / 2, TAM / 2 + 12);
      ctx.stroke();
      ctx.restore();
    }
  } catch (e) {
    // mesmo que o desenho em si falhe por algum motivo, ainda posiciona e
    // mostra a lupa (com o conteúdo que sobrou) -- melhor que desaparecer
    // silenciosamente sem dar nenhuma pista visual do que está errado.
  }

  const larguraTela = wrap.clientWidth || (TAM + 8);
  const left = Math.max(4, Math.min(larguraTela - TAM - 4, dispX - TAM / 2));
  const GAP = 48;
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

// Pasta de destino: por padrão só deixa ESCOLHER entre as pastas que já
// existem (evita duplicar pasta por erro de digitação/acento), e só mostra
// um campo de texto livre quando o usuário pede explicitamente "Nova pasta".
function escAlternarPasta(nova) {
  const modoExistente = document.getElementById('esc-pasta-modo-existente');
  const modoNova = document.getElementById('esc-pasta-modo-nova');
  if (modoExistente) modoExistente.style.display = nova ? 'none' : '';
  if (modoNova) modoNova.style.display = nova ? '' : 'none';
  if (nova) {
    const input = document.getElementById('esc-pasta-nova');
    if (input) input.focus();
  }
}
function escPastaAtual() {
  const modoNova = document.getElementById('esc-pasta-modo-nova');
  if (modoNova && modoNova.style.display !== 'none') {
    const input = document.getElementById('esc-pasta-nova');
    return (input && input.value.trim()) || 'Geral';
  }
  const sel = document.getElementById('esc-pasta-select');
  return (sel && sel.value) || 'Geral';
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
  escPaginas.push({ canvas: canvasFinal, filtro: 'original' });
  document.getElementById('esc-overlay').style.display = 'none';
  escImgAtual = null;
  escEsconderLupa();
  escRenderPaginas();
}

const ESC_FILTROS = [
  { v: 'original', l: 'Original (cor)' },
  { v: 'cinza', l: 'Cinza' },
  { v: 'pb', l: 'Preto e branco' },
  { v: 'realce', l: 'Realce de contraste' },
];

function escAplicarFiltro(canvasOrigem, tipo) {
  if (!tipo || tipo === 'original') return canvasOrigem;
  const c = document.createElement('canvas');
  c.width = canvasOrigem.width; c.height = canvasOrigem.height;
  const ctx = c.getContext('2d');
  ctx.drawImage(canvasOrigem, 0, 0);
  const img = ctx.getImageData(0, 0, c.width, c.height);
  const d = img.data;
  for (let i = 0; i < d.length; i += 4) {
    if (tipo === 'cinza') {
      const g = 0.299 * d[i] + 0.587 * d[i + 1] + 0.114 * d[i + 2];
      d[i] = d[i + 1] = d[i + 2] = g;
    } else if (tipo === 'pb') {
      // escala de cinza + contraste forte -- aproxima da "página escaneada"
      // clássica (fundo bem branco, texto bem preto)
      let g = 0.299 * d[i] + 0.587 * d[i + 1] + 0.114 * d[i + 2];
      g = Math.min(255, Math.max(0, (g - 128) * 1.8 + 128));
      d[i] = d[i + 1] = d[i + 2] = g;
    } else if (tipo === 'realce') {
      // mantém a cor, mas reforça contraste -- bom pra tinta apagada/papel
      // amarelado sem perder a cor do documento
      d[i] = Math.min(255, Math.max(0, (d[i] - 128) * 1.3 + 128 + 6));
      d[i + 1] = Math.min(255, Math.max(0, (d[i + 1] - 128) * 1.3 + 128 + 6));
      d[i + 2] = Math.min(255, Math.max(0, (d[i + 2] - 128) * 1.3 + 128 + 6));
    }
  }
  ctx.putImageData(img, 0, 0);
  return c;
}

function escRenderPaginas() {
  const cont = document.getElementById('esc-paginas');
  cont.innerHTML = '';
  escPaginas.forEach((pg, idx) => {
    const exibicao = escAplicarFiltro(pg.canvas, pg.filtro);
    const col = document.createElement('div');
    col.className = 'col-6 col-md-3 col-lg-2';
    const opcoes = ESC_FILTROS.map(f => `<option value="${f.v}" ${f.v === pg.filtro ? 'selected' : ''}>${f.l}</option>`).join('');
    col.innerHTML = `
      <div class="card h-100">
        <div class="card-body p-2 text-center">
          <img src="${exibicao.toDataURL('image/jpeg', 0.7)}" class="img-fluid rounded mb-1" style="max-height:160px; object-fit:contain;">
          <div class="small text-muted">Página ${idx + 1}</div>
          <select class="form-select form-select-sm mt-1" onchange="escDefinirFiltro(${idx}, this.value)">${opcoes}</select>
          <button type="button" class="btn btn-outline-danger btn-sm w-100 mt-1" onclick="escRemoverPagina(${idx})"><i class="fas fa-trash me-1"></i>Remover</button>
        </div>
      </div>`;
    cont.appendChild(col);
  });
  document.getElementById('esc-contador').textContent = escPaginas.length;
  document.getElementById('esc-card-salvar').style.display = escPaginas.length ? 'block' : 'none';
}

function escDefinirFiltro(idx, tipo) { escPaginas[idx].filtro = tipo; escRenderPaginas(); }
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
    fd.append('pasta', escPastaAtual());
    fd.append('nome', document.getElementById('esc-nome').value || '');
    for (const pg of escPaginas) {
      const canvasFinal = escAplicarFiltro(pg.canvas, pg.filtro);
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
