/* ============================================================
   MindForge — assets/main.js
   零依赖 · 原生 ES5/ES2017 兼容写法 · IIFE 隔离作用域
   ------------------------------------------------------------
   模块
   01 工具函数
   02 MemoryField —— 记忆粒子网络（canvas）
   03 导航：吸顶态 / 抽屉菜单 / 锚点高亮
   04 滚动揭示 IntersectionObserver
   05 图表入场：召回环形图 / 遗忘曲线 / 堆叠条 / 数字滚动
   06 代码复制
   ============================================================ */

(function () {
  'use strict';

  /* ============================ 01 工具函数 ============================ */

  /** 是否要求降低动效（用户系统设置）。 */
  var prefersReducedMotion = false;
  try {
    prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  } catch (err) {
    prefersReducedMotion = false;
  }

  /** @type {boolean} 是否支持 IntersectionObserver（老浏览器降级用）。 */
  var hasIO = typeof window.IntersectionObserver === 'function';

  /**
   * 安全查询单个元素。
   * @param {string} selector CSS 选择器
   * @param {ParentNode=} scope 查找范围，默认 document
   * @return {Element|null}
   */
  function qs(selector, scope) {
    return (scope || document).querySelector(selector);
  }

  /**
   * 安全查询多个元素并转为数组。
   * @param {string} selector CSS 选择器
   * @param {ParentNode=} scope 查找范围，默认 document
   * @return {Array<Element>}
   */
  function qsa(selector, scope) {
    return Array.prototype.slice.call((scope || document).querySelectorAll(selector));
  }

  /**
   * 限制数值区间。
   * @param {number} v 输入值
   * @param {number} min 下界
   * @param {number} max 上界
   * @return {number}
   */
  function clamp(v, min, max) {
    return v < min ? min : (v > max ? max : v);
  }

  /**
   * 防抖包装。
   * @param {Function} fn 目标函数
   * @param {number} wait 等待毫秒
   * @return {Function}
   */
  function debounce(fn, wait) {
    var timer = null;
    return function () {
      var args = arguments;
      var self = this;
      if (timer) { window.clearTimeout(timer); }
      timer = window.setTimeout(function () { fn.apply(self, args); }, wait);
    };
  }

  /**
   * 读取元素的整数型 data 属性。
   * @param {Element} el 元素
   * @param {string} name 属性名（不含 data- 前缀）
   * @param {number} fallback 缺省值
   * @return {number}
   */
  function dataInt(el, name, fallback) {
    var raw = el.getAttribute('data-' + name);
    var n = parseInt(raw, 10);
    return isNaN(n) ? fallback : n;
  }

  /* ============================ 02 记忆粒子网络 ============================ */
  /**
   * MemoryField —— 「记忆被激活」隐喻的粒子网络。
   *
   * 算法思路
   *  - 节点在视口内做极低速随机漂移（速度上限 ~0.18 px/frame@60fps），
   *    越界后从另一侧环绕回场，保证密度恒定。
   *  - 邻接判定使用「均匀空间网格」（cell = 连线半径），
   *    每个节点只需检查 3x3 邻域，把 O(n²) 降到近似 O(n·k)，
   *    130 个节点时每帧的候选对约 400 组而非 16,900 组。
   *  - 连线透明度按距离线性衰减，并把 alpha 量化成 5 个档位，
   *    同档位合并进一条 Path2D 一次 stroke，避免上百次状态切换。
   *  - 指针靠近时给节点注入 activation（0~1），逐帧指数衰减；
   *    激活节点半径变大、连线更亮，形成「记忆被点亮」的观感。
   *
   * 性能考量
   *  - DPR 上限 2（移动端 1.5），避免高倍屏下像素量爆炸。
   *  - 节点数按面积自适应：桌面峰值 130，平板 78，移动端 46。
   *  - IntersectionObserver：Hero 离屏即停 rAF；
   *    document.hidden 时同样停帧。
   *  - resize 走 160ms 防抖，避免连续重建。
   *  - prefers-reduced-motion：只绘制一帧静态图，不启动循环。
   */
  function MemoryField(canvas, options) {
    var opt = options || {};

    this.canvas = canvas;
    this.ctx = canvas.getContext('2d', { alpha: true });

    this.linkDist = opt.linkDist || 132;      // 连线半径（CSS 像素）
    this.pointerRadius = opt.pointerRadius || 178; // 指针激活半径
    this.baseAlpha = opt.baseAlpha || 0.16;   // 连线基础透明度
    this.nodeAlpha = opt.nodeAlpha || 0.42;   // 节点基础透明度

    this.palette = opt.palette || ['34, 211, 238', '129, 140, 248', '168, 85, 247'];

    this.w = 0;
    this.h = 0;
    this.dpr = 1;
    this.nodes = [];
    this.grid = [];
    this.cols = 0;
    this.rows = 0;
    this.cell = this.linkDist;

    this.pointer = { x: -9999, y: -9999, active: false };
    this.rafId = 0;
    this.lastTs = 0;
    this.running = false;
    this.visible = true;

    this._onResize = debounce(this.resize.bind(this), 160);
    this._onPointerMove = this._handlePointerMove.bind(this);
    this._onPointerLeave = this._handlePointerLeave.bind(this);
    this._onVisibility = this._handleVisibility.bind(this);
    this._onFrame = this._frame.bind(this);

    this._init();
  }

  /** 初始化尺寸、节点与事件监听。 */
  MemoryField.prototype._init = function () {
    this.resize();

    window.addEventListener('resize', this._onResize, { passive: true });
    window.addEventListener('orientationchange', this._onResize, { passive: true });
    document.addEventListener('visibilitychange', this._onVisibility);

    if (!prefersReducedMotion) {
      window.addEventListener('pointermove', this._onPointerMove, { passive: true });
      window.addEventListener('pointerdown', this._onPointerMove, { passive: true });
      window.addEventListener('pointerleave', this._onPointerLeave, { passive: true });
      window.addEventListener('blur', this._onPointerLeave);
    }

    if (hasIO) {
      var self = this;
      var io = new IntersectionObserver(function (entries) {
        self.visible = entries[0].isIntersecting;
        if (self.visible) { self.start(); } else { self.stop(); }
      }, { threshold: 0 });
      io.observe(this.canvas);
    }

    if (prefersReducedMotion) {
      this._render(0);
    } else {
      this.start();
    }
  };

  /** 计算画布尺寸、DPR 与节点数量，并重建节点数组。 */
  MemoryField.prototype.resize = function () {
    var rect = this.canvas.getBoundingClientRect();
    var w = Math.max(1, Math.round(rect.width || window.innerWidth));
    var h = Math.max(1, Math.round(rect.height || window.innerHeight));

    this.w = w;
    this.h = h;
    this.dpr = Math.min(window.devicePixelRatio || 1, w < 768 ? 1.5 : 2);

    this.canvas.width = Math.round(w * this.dpr);
    this.canvas.height = Math.round(h * this.dpr);
    this.ctx.setTransform(this.dpr, 0, 0, this.dpr, 0, 0);

    // 连线半径随视口收缩，移动端不要用桌面尺度
    if (w < 768) {
      this.linkDist = 104;
      this.pointerRadius = 140;
    } else if (w < 1280) {
      this.linkDist = 120;
      this.pointerRadius = 160;
    } else {
      this.linkDist = 132;
      this.pointerRadius = 178;
    }
    this.cell = this.linkDist;

    this._buildNodes();
    if (prefersReducedMotion) { this._render(0); }
  };

  /** 按视口面积重建节点（密度自适应，移动端显著减少）。 */
  MemoryField.prototype._buildNodes = function () {
    var area = this.w * this.h;
    var cap = this.w < 768 ? 46 : (this.w < 1280 ? 78 : 130);
    var count = clamp(Math.round(area / 15000), 22, cap);

    this.nodes.length = 0;
    for (var i = 0; i < count; i++) {
      this.nodes.push({
        x: Math.random() * this.w,
        y: Math.random() * this.h,
        vx: (Math.random() - 0.5) * 0.36,
        vy: (Math.random() - 0.5) * 0.36,
        r: 0.9 + Math.random() * 1.35,
        c: (Math.random() * this.palette.length) | 0,
        ph: Math.random() * Math.PI * 2,       // 呼吸相位
        sp: 0.006 + Math.random() * 0.012,     // 呼吸速度
        act: 0                                  // 激活度 0~1
      });
    }

    // 轻微阻尼，避免长时间运行后出现「整场同向漂移」
    for (var j = 0; j < this.nodes.length; j++) {
      var n = this.nodes[j];
      n.vx *= 0.85;
      n.vy *= 0.85;
    }

    this.cols = Math.max(1, Math.ceil(this.w / this.cell));
    this.rows = Math.max(1, Math.ceil(this.h / this.cell));
    this.grid = new Array(this.cols * this.rows);
  };

  /** 把节点投放到空间网格桶中。 */
  MemoryField.prototype._fillGrid = function () {
    for (var i = 0; i < this.grid.length; i++) { this.grid[i] = null; }
    for (var k = 0; k < this.nodes.length; k++) {
      var n = this.nodes[k];
      var gx = clamp((n.x / this.cell) | 0, 0, this.cols - 1);
      var gy = clamp((n.y / this.cell) | 0, 0, this.rows - 1);
      var idx = gy * this.cols + gx;
      if (!this.grid[idx]) { this.grid[idx] = []; }
      this.grid[idx].push(n);
    }
  };

  /** 指针移动：记录位置。 */
  MemoryField.prototype._handlePointerMove = function (evt) {
    var rect = this.canvas.getBoundingClientRect();
    var x = evt.clientX - rect.left;
    var y = evt.clientY - rect.top;
    if (x < -80 || y < -80 || x > rect.width + 80 || y > rect.height + 80) {
      this.pointer.active = false;
      return;
    }
    this.pointer.x = x;
    this.pointer.y = y;
    this.pointer.active = true;
  };

  /** 指针离开：停止激活。 */
  MemoryField.prototype._handlePointerLeave = function () {
    this.pointer.active = false;
    this.pointer.x = -9999;
    this.pointer.y = -9999;
  };

  /** 页面不可见时停帧，回到前台恢复。 */
  MemoryField.prototype._handleVisibility = function () {
    if (document.hidden) { this.stop(); }
    else if (this.visible && !prefersReducedMotion) { this.start(); }
  };

  /** 启动动画循环。 */
  MemoryField.prototype.start = function () {
    if (this.running || prefersReducedMotion || document.hidden) { return; }
    this.running = true;
    this.lastTs = 0;
    this.rafId = window.requestAnimationFrame(this._onFrame);
  };

  /** 停止动画循环并释放 rAF。 */
  MemoryField.prototype.stop = function () {
    this.running = false;
    if (this.rafId) {
      window.cancelAnimationFrame(this.rafId);
      this.rafId = 0;
    }
  };

  /** rAF 回调：按时间差推进，避免高刷屏速度翻倍。 */
  MemoryField.prototype._frame = function (ts) {
    if (!this.running) { return; }
    var dt = this.lastTs ? (ts - this.lastTs) : 16.67;
    this.lastTs = ts;
    // 掉帧/切后台回来时钳制步长，防止节点「瞬移」
    var step = clamp(dt / 16.67, 0.25, 2.5);
    this._render(step);
    this.rafId = window.requestAnimationFrame(this._onFrame);
  };

  /** 推进一帧并绘制。 */
  MemoryField.prototype._render = function (step) {
    var ctx = this.ctx;
    var i, n;

    for (i = 0; i < this.nodes.length; i++) {
      n = this.nodes[i];

      n.x += n.vx * step;
      n.y += n.vy * step;

      // 环绕回场
      if (n.x < -20) { n.x = this.w + 20; }
      else if (n.x > this.w + 20) { n.x = -20; }
      if (n.y < -20) { n.y = this.h + 20; }
      else if (n.y > this.h + 20) { n.y = -20; }

      n.ph += n.sp * step;

      // 指针激活：近距离充能，逐帧指数衰减
      if (this.pointer.active) {
        var dx = n.x - this.pointer.x;
        var dy = n.y - this.pointer.y;
        var d2 = dx * dx + dy * dy;
        var pr = this.pointerRadius;
        if (d2 < pr * pr) {
          var a = 1 - Math.sqrt(d2) / pr;
          if (a > n.act) { n.act = a; }
        }
      }
      n.act *= Math.pow(0.935, step);
      if (n.act < 0.002) { n.act = 0; }
    }

    this._fillGrid();
    this._draw();
  };

  /** 绘制连线与节点。 */
  MemoryField.prototype._draw = function () {
    var ctx = this.ctx;
    ctx.clearRect(0, 0, this.w, this.h);

    var linkDist = this.linkDist;
    var linkDist2 = linkDist * linkDist;
    var buckets = [[], [], [], [], []];   // 5 档 alpha 桶
    var THRESH = linkDist * 0.78;         // 只在实际可见范围内连线，省掉尾部计算
    var THRESH2 = THRESH * THRESH;

    for (var gy = 0; gy < this.rows; gy++) {
      for (var gx = 0; gx < this.cols; gx++) {
        var cellNodes = this.grid[gy * this.cols + gx];
        if (!cellNodes) { continue; }

        // 3x3 邻域（只取右/下半区，避免重复配对）
        for (var oy = 0; oy <= 1; oy++) {
          for (var ox = -1; ox <= 1; ox++) {
            if (oy === 0 && ox < 0) { continue; }
            var nx = gx + ox;
            var ny = gy + oy;
            if (nx < 0 || ny < 0 || nx >= this.cols || ny >= this.rows) { continue; }
            var other = this.grid[ny * this.cols + nx];
            if (!other) { continue; }

            var sameCell = (ox === 0 && oy === 0);
            for (var a = 0; a < cellNodes.length; a++) {
              var p = cellNodes[a];
              var startIdx = sameCell ? a + 1 : 0;
              for (var b = startIdx; b < other.length; b++) {
                var q = other[b];
                var dx = p.x - q.x;
                var dy = p.y - q.y;
                var d2 = dx * dx + dy * dy;
                if (d2 > THRESH2) { continue; }

                var t = 1 - Math.sqrt(d2) / linkDist;
                var boost = 1 + (p.act + q.act) * 1.9;
                var alpha = this.baseAlpha * t * t * boost;
                if (alpha < 0.012) { continue; }

                var lvl = alpha > 0.30 ? 4 : (alpha > 0.18 ? 3 : (alpha > 0.09 ? 2 : (alpha > 0.04 ? 1 : 0)));
                buckets[lvl].push(p.x, p.y, q.x, q.y);
              }
            }
          }
        }
      }
    }

    ctx.lineWidth = 1;
    for (var lvl = 0; lvl < buckets.length; lvl++) {
      var pts = buckets[lvl];
      if (!pts.length) { continue; }
      ctx.beginPath();
      for (var k = 0; k < pts.length; k += 4) {
        ctx.moveTo(pts[k], pts[k + 1]);
        ctx.lineTo(pts[k + 2], pts[k + 3]);
      }
      // 各档取中值 alpha：0.022 / 0.062 / 0.13 / 0.24 / 0.40
      ctx.strokeStyle = 'rgba(129, 178, 220, ' + [0.022, 0.062, 0.13, 0.24, 0.40][lvl] + ')';
      ctx.stroke();
    }

    // 节点
    for (var i = 0; i < this.nodes.length; i++) {
      var n = this.nodes[i];
      var breathe = 0.78 + Math.sin(n.ph) * 0.22;
      var alpha = clamp(this.nodeAlpha * breathe + n.act * 0.55, 0, 1);
      var radius = n.r * (1 + n.act * 1.5);
      var rgb = this.palette[n.c];

      if (n.act > 0.02) {
        // 激活光晕：用一层大半径低透明度圆代替 shadowBlur，开销更低
        ctx.beginPath();
        ctx.arc(n.x, n.y, radius * 5.2, 0, Math.PI * 2);
        ctx.fillStyle = 'rgba(' + rgb + ',' + (n.act * 0.085).toFixed(3) + ')';
        ctx.fill();
      }

      ctx.beginPath();
      ctx.arc(n.x, n.y, radius, 0, Math.PI * 2);
      ctx.fillStyle = 'rgba(' + rgb + ',' + alpha.toFixed(3) + ')';
      ctx.fill();
    }
  };

  /* ============================ 03 导航 ============================ */

  /** 吸顶态：用哨兵元素的 IntersectionObserver 代替 scroll 监听。 */
  function initNavScrollState() {
    var nav = qs('.nav');
    var sentinel = qs('#nav-sentinel');
    if (!nav || !sentinel || !hasIO) { return; }

    var io = new IntersectionObserver(function (entries) {
      if (entries[0].isIntersecting) {
        nav.classList.remove('is-scrolled');
      } else {
        nav.classList.add('is-scrolled');
      }
    }, { threshold: 0, rootMargin: '0px' });
    io.observe(sentinel);
  }

  /** 移动端抽屉菜单。 */
  function initNavDrawer() {
    var toggle = qs('#nav-toggle');
    var drawer = qs('#nav-drawer');
    if (!toggle || !drawer) { return; }

    var isOpen = false;

    function setOpen(next) {
      isOpen = next;
      toggle.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
      drawer.classList.toggle('is-open', isOpen);
      drawer.setAttribute('aria-hidden', isOpen ? 'false' : 'true');
    }

    toggle.addEventListener('click', function () { setOpen(!isOpen); });

    // 点击抽屉内锚点后自动收起
    qsa('a[href^="#"]', drawer).forEach(function (link) {
      link.addEventListener('click', function () { setOpen(false); });
    });

    document.addEventListener('keydown', function (evt) {
      if (evt.key === 'Escape' && isOpen) { setOpen(false); toggle.focus(); }
    });

    document.addEventListener('click', function (evt) {
      if (!isOpen) { return; }
      if (drawer.contains(evt.target) || toggle.contains(evt.target)) { return; }
      setOpen(false);
    });

    setOpen(false);
  }

  /** 当前区块对应的导航锚点高亮。 */
  function initActiveAnchor() {
    var links = qsa('.nav-links a[href^="#"]');
    if (!links.length || !hasIO) { return; }

    var map = {};
    var targets = [];
    links.forEach(function (link) {
      var id = link.getAttribute('href').slice(1);
      if (!id) { return; }
      var section = document.getElementById(id);
      if (!section) { return; }
      map[id] = link;
      targets.push(section);
    });
    if (!targets.length) { return; }

    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) { return; }
        var link = map[entry.target.id];
        if (!link) { return; }
        links.forEach(function (l) { l.classList.remove('is-active'); });
        link.classList.add('is-active');
      });
    }, { rootMargin: '-45% 0px -50% 0px', threshold: 0 });

    targets.forEach(function (t) { io.observe(t); });
  }

  /* ============================ 04 滚动揭示 ============================ */

  /** 通用入场观察器：命中后加 .is-in 并停止观察。 */
  function initReveal() {
    var items = qsa('[data-reveal]');
    if (!items.length) { return; }

    if (!hasIO || prefersReducedMotion) {
      items.forEach(function (el) { el.classList.add('is-in'); });
      return;
    }

    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) { return; }
        entry.target.classList.add('is-in');
        io.unobserve(entry.target);
      });
    }, { threshold: 0.12, rootMargin: '0px 0px -8% 0px' });

    items.forEach(function (el) { io.observe(el); });
  }

  /* ============================ 05 图表入场 ============================ */

  /** 召回权重环形图：进入视口时按百分比铺开弧段。 */
  function initRecallDonut() {
    var donut = qs('#recall-donut');
    if (!donut) { return; }

    var segs = qsa('.seg', donut);
    if (!segs.length) { return; }

    var cx = parseFloat(donut.getAttribute('data-cx')) || 140;
    var cy = parseFloat(donut.getAttribute('data-cy')) || 140;
    var r = parseFloat(donut.getAttribute('data-r')) || 104;
    var circumference = 2 * Math.PI * r;
    var gap = 5; // 弧段之间的视觉留白（弧长单位）

    function paint() {
      var cursor = 0;
      segs.forEach(function (seg) {
        var pct = parseFloat(seg.getAttribute('data-pct')) || 0;
        var len = Math.max(0, circumference * (pct / 100) - gap);
        var startAngle = (cursor / 100) * 360 - 90;
        seg.setAttribute('transform', 'rotate(' + startAngle.toFixed(2) + ' ' + cx + ' ' + cy + ')');
        seg.setAttribute('stroke-dasharray', len.toFixed(2) + ' ' + (circumference - len).toFixed(2));
        cursor += pct;
      });
    }

    if (prefersReducedMotion || !hasIO) {
      paint();
      return;
    }

    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) { return; }
        paint();
        io.unobserve(entry.target);
      });
    }, { threshold: 0.3 });
    io.observe(donut);
  }

  /** 数字滚动：仅对带 data-count 的元素生效。 */
  function initCounters() {
    var items = qsa('[data-count]');
    if (!items.length) { return; }

    function run(el) {
      var target = dataInt(el, 'count', 0);
      var suffix = el.getAttribute('data-suffix') || '';
      var duration = 1100;
      var startTime = 0;

      if (prefersReducedMotion) {
        el.textContent = String(target) + suffix;
        return;
      }

      function tick(ts) {
        if (!startTime) { startTime = ts; }
        var p = clamp((ts - startTime) / duration, 0, 1);
        var eased = 1 - Math.pow(1 - p, 3);
        el.textContent = String(Math.round(target * eased)) + suffix;
        if (p < 1) { window.requestAnimationFrame(tick); }
      }
      window.requestAnimationFrame(tick);
    }

    if (!hasIO) {
      items.forEach(run);
      return;
    }

    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) { return; }
        run(entry.target);
        io.unobserve(entry.target);
      });
    }, { threshold: 0.4 });
    items.forEach(function (el) { io.observe(el); });
  }

  /* ============================ 06 代码复制 ============================ */

  /** 代码复制按钮：复制目标元素的纯文本。 */
  function initCopyButtons() {
    var buttons = qsa('[data-copy]');
    if (!buttons.length) { return; }

    buttons.forEach(function (btn) {
      var selector = btn.getAttribute('data-copy');
      var target = selector ? qs(selector) : null;
      if (!target) { return; }

      var label = btn.querySelector('.copy-label');
      var defaultText = label ? label.textContent : '';
      var timer = null;

      function flash(ok) {
        btn.classList.add('is-done');
        if (label) { label.textContent = ok ? '已复制' : '复制失败'; }
        if (timer) { window.clearTimeout(timer); }
        timer = window.setTimeout(function () {
          btn.classList.remove('is-done');
          if (label) { label.textContent = defaultText; }
        }, 1900);
      }

      btn.addEventListener('click', function () {
        var text = target.textContent || target.innerText || '';
        text = text.replace(/\s+$/, '');

        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(text).then(function () { flash(true); }, function () { flash(false); });
          return;
        }
        // 降级：execCommand
        try {
          var ta = document.createElement('textarea');
          ta.value = text;
          ta.setAttribute('readonly', 'readonly');
          ta.style.position = 'fixed';
          ta.style.top = '-1000px';
          ta.style.opacity = '0';
          document.body.appendChild(ta);
          ta.select();
          var ok = document.execCommand('copy');
          document.body.removeChild(ta);
          flash(ok);
        } catch (err) {
          flash(false);
        }
      });
    });
  }

  /* ============================ 启动 ============================ */

  /**
   * DOM 就绪后引导所有模块。
   */
  function boot() {
    var canvas = qs('#memory-canvas');
    if (canvas) {
      try {
        new MemoryField(canvas, {});
      } catch (err) {
        // canvas 不可用时静默降级，页面其余功能不受影响
        canvas.style.display = 'none';
      }
    }

    initNavScrollState();
    initNavDrawer();
    initActiveAnchor();
    initReveal();
    initRecallDonut();
    initCounters();
    initCopyButtons();

    // 年份
    var yearEl = qs('#foot-year');
    if (yearEl) { yearEl.textContent = String(new Date().getFullYear()); }

    // 版本号注入：读取 JSON-LD 中的 softwareVersion，统一替换所有 [data-ver] 元素
    var ver = '';
    try {
      var ld = document.querySelector('script[type="application/ld+json"]');
      if (ld) { ver = JSON.parse(ld.textContent).softwareVersion || ''; }
    } catch (e) {}
    if (ver) {
      document.querySelectorAll('[data-ver]').forEach(function (el) {
        el.textContent = el.dataset.verTpl ? el.dataset.verTpl.replace('{v}', ver) : 'v' + ver;
      });
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
