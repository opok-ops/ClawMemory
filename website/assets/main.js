document.addEventListener('DOMContentLoaded', () => {
  initCursorGlow();
  initRipple();
  initParticles();
  initScrollReveal();
  initCounters();
  initCodeTabs();
  initPlayground();
  initKnowledgeGraph();
  initNavScroll();
});

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = String(str == null ? '' : str);
    return div.innerHTML;
}

/* v5.0.7: 点击涟漪效果 */
function initRipple() {
  document.addEventListener('click', (e) => {
    const ripple = document.createElement('div');
    ripple.className = 'ripple';
    ripple.style.left = (e.clientX - 60) + 'px';
    ripple.style.top = (e.clientY - 60) + 'px';
    document.body.appendChild(ripple);

    ripple.addEventListener('animationend', () => {
      ripple.remove();
    });
  });
}

function initCursorGlow() {
  const glow = document.getElementById('cursorGlow');
  if (!glow) return;

  let mouseX = 0, mouseY = 0;
  let glowX = 0, glowY = 0;

  document.addEventListener('mousemove', (e) => {
    mouseX = e.clientX;
    mouseY = e.clientY;
  });

  function animate() {
    glowX += (mouseX - glowX) * 0.1;
    glowY += (mouseY - glowY) * 0.1;
    glow.style.left = glowX + 'px';
    glow.style.top = glowY + 'px';
    requestAnimationFrame(animate);
  }
  animate();

  document.addEventListener('mouseenter', () => glow.style.opacity = '1');
  document.addEventListener('mouseleave', () => glow.style.opacity = '0');
}

function initParticles() {
  const canvas = document.getElementById('particle-canvas');
  if (!canvas) return;

  const ctx = canvas.getContext('2d');
  let width, height;
  let particles = [];
  const PARTICLE_COUNT = 80;

  function resize() {
    width = canvas.width = window.innerWidth;
    height = canvas.height = window.innerHeight;
  }

  class Particle {
    constructor() {
      this.reset();
    }
    reset() {
      this.x = Math.random() * width;
      this.y = Math.random() * height;
      this.vx = (Math.random() - 0.5) * 0.3;
      this.vy = (Math.random() - 0.5) * 0.3;
      this.radius = Math.random() * 1.5 + 0.5;
      this.opacity = Math.random() * 0.5 + 0.2;
    }
    update() {
      this.x += this.vx;
      this.y += this.vy;
      if (this.x < 0 || this.x > width) this.vx *= -1;
      if (this.y < 0 || this.y > height) this.vy *= -1;
    }
    draw() {
      ctx.beginPath();
      ctx.arc(this.x, this.y, this.radius, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(0, 212, 255, ${this.opacity})`;
      ctx.fill();
    }
  }

  function init() {
    resize();
    particles = [];
    for (let i = 0; i < PARTICLE_COUNT; i++) {
      particles.push(new Particle());
    }
  }

  function drawLines() {
    for (let i = 0; i < particles.length; i++) {
      for (let j = i + 1; j < particles.length; j++) {
        const dx = particles[i].x - particles[j].x;
        const dy = particles[i].y - particles[j].y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < 150) {
          ctx.beginPath();
          ctx.moveTo(particles[i].x, particles[i].y);
          ctx.lineTo(particles[j].x, particles[j].y);
          ctx.strokeStyle = `rgba(168, 85, 247, ${0.1 * (1 - dist / 150)})`;
          ctx.lineWidth = 0.5;
          ctx.stroke();
        }
      }
    }
  }

  function animate() {
    ctx.clearRect(0, 0, width, height);
    particles.forEach(p => {
      p.update();
      p.draw();
    });
    drawLines();
    requestAnimationFrame(animate);
  }

  init();
  animate();
  window.addEventListener('resize', init);
}

function initScrollReveal() {
  const reveals = document.querySelectorAll('.reveal');
  if (!reveals.length) return;

  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add('visible');
        observer.unobserve(entry.target);
      }
    });
  }, {
    threshold: 0.1,
    rootMargin: '0px 0px -50px 0px'
  });

  reveals.forEach(el => observer.observe(el));
}

function initCounters() {
  const counters = document.querySelectorAll('.stat-value[data-target]');
  if (!counters.length) return;

  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        animateCounter(entry.target);
        observer.unobserve(entry.target);
      }
    });
  }, { threshold: 0.5 });

  counters.forEach(c => observer.observe(c));
}

function animateCounter(el) {
  const target = parseInt(el.dataset.target);
  const duration = 1500;
  const start = performance.now();

  function update(now) {
    const progress = Math.min((now - start) / duration, 1);
    const eased = 1 - Math.pow(1 - progress, 3);
    const current = Math.floor(eased * target);
    el.textContent = current;
    if (progress < 1) requestAnimationFrame(update);
    else el.textContent = target;
  }
  requestAnimationFrame(update);
}

function initCodeTabs() {
  const tabs = document.querySelectorAll('.code-tab');
  const blocks = document.querySelectorAll('.code-block');
  if (!tabs.length) return;

  tabs.forEach(tab => {
    tab.addEventListener('click', () => {
      const target = tab.dataset.tab;
      tabs.forEach(t => t.classList.remove('active'));
      blocks.forEach(b => b.classList.remove('active'));
      tab.classList.add('active');
      document.getElementById(`tab-${target}`)?.classList.add('active');
    });
  });
}

const DEMO_MEMORIES = [
  { id: '1', title: '关于数据库优化的想法', content: '今天研究了 PostgreSQL 查询优化，发现索引对大表查询性能提升显著。建议对经常出现在 WHERE 子句中的列创建复合索引，注意索引顺序要匹配查询模式。另外，VACUUM ANALYZE 可以帮助规划器生成更好的执行计划。', category: 'tech', catColor: 'cat-purple', tags: ['数据库', 'PostgreSQL', '性能优化'], importance: 'high', time: '2小时前' },
  { id: '2', title: '项目周报总结', content: '本周完成了用户认证模块的重构，从 session-based 迁移到 JWT + refresh token 方案。上线后性能提升 30%，但需要注意 token 刷新的并发安全问题。下周计划开始做支付模块集成。', category: 'work', catColor: 'cat-blue', tags: ['工作', '周报', 'JWT'], importance: 'medium', time: '5小时前' },
  { id: '3', title: '周末徒步路线推荐', content: '朋友推荐了一条难度适中的徒步路线，全程约12公里，海拔上升800米。途经一片枫树林，秋天景色应该很美。需要准备登山杖、足够的水和能量棒。计划下周六早上7点出发。', category: 'life', catColor: 'cat-green', tags: ['生活', '徒步', '运动'], importance: 'low', time: '昨天' },
  { id: '4', title: '新产品创意：AI写作助手', content: '想到一个可以根据用户写作风格自动调整语气的AI助手。核心功能包括：风格学习、语气转换、结构建议、修辞优化。目标用户是内容创作者和文案写作者。需要研究一下现有竞品的差异化空间。', category: 'idea', catColor: 'cat-orange', tags: ['创意', 'AI', '产品'], importance: 'high', time: '2天前' },
  { id: '5', title: 'Python 装饰器最佳实践', content: '整理了 Python 装饰器的几种常见模式：函数装饰器、带参数的装饰器、类装饰器、使用 functools.wraps 保留元数据。特别注意装饰器的执行顺序和可组合性。建议项目中统一使用类装饰器来管理复杂逻辑。', category: 'tech', catColor: 'cat-purple', tags: ['Python', '装饰器', '编程'], importance: 'medium', time: '3天前' },
  { id: '6', title: '用户喜欢的编程语言', content: '根据历史对话分析，用户最常用的编程语言是 Python，其次是 TypeScript。对函数式编程风格有偏好，喜欢简洁的代码表达。在选择技术方案时倾向于轻量级、社区活跃的方案。', category: 'tech', catColor: 'cat-purple', tags: ['偏好', 'Python', 'TypeScript'], importance: 'medium', time: '1周前' },
  { id: '7', title: '咖啡豆采购清单', content: '准备补充咖啡豆库存：1. 埃塞俄比亚耶加雪菲（花香果调，手冲用）；2. 哥伦比亚苏普雷莫（均衡醇厚，法压用）；3. 印尼曼特宁（浓郁低酸，意式用）。建议每种买250g，注意烘焙日期在两周内的最新鲜。', category: 'life', catColor: 'cat-green', tags: ['咖啡', '购物', '生活'], importance: 'low', time: '1周前' },
  { id: '8', title: '设计系统规范建议', content: '新项目需要建立完整的设计系统：颜色（主色/辅助色/中性色/语义色）、字体层级（H1-H6/正文/辅助）、间距系统（4px基数）、组件库（按钮/表单/卡片/导航）。建议使用 Design Tokens 统一管理，支持暗色模式切换。', category: 'work', catColor: 'cat-blue', tags: ['设计', 'UI', '设计系统'], importance: 'high', time: '2周前' },
  { id: '9', title: '梦境记录：未来城市', content: '昨晚梦见一座悬浮在空中的城市，建筑是透明的水晶材质，人们通过光带移动。城市中央有一棵巨大的发光树，据说是城市的能量核心。醒来后画面感依然很清晰，可以作为科幻故事的灵感。', category: 'idea', catColor: 'cat-orange', tags: ['梦境', '科幻', '灵感'], importance: 'low', time: '2周前' },
  { id: '10', title: '技术债务清单', content: '整理当前项目的技术债务：1. 旧版 API 兼容层需要清理；2. 单元测试覆盖率不足 60%；3. 部分模块缺少类型定义；4. CI/CD 流水线速度慢。优先级排序：测试覆盖 > 类型定义 > API清理 > CI优化。', category: 'work', catColor: 'cat-blue', tags: ['技术债务', '工程', '规划'], importance: 'medium', time: '3周前' },
];

function initPlayground() {
  const memoryList = document.getElementById('memoryList');
  const searchInput = document.getElementById('searchInput');
  const searchBtn = document.getElementById('searchBtn');
  const searchResults = document.getElementById('searchResults');
  const categoryBtns = document.querySelectorAll('.pg-cat');

  if (!memoryList) return;

  let currentCategory = 'all';
  let selectedId = null;

  function renderMemoryList(memories) {
    memoryList.innerHTML = memories.map(m => `
      <div class="pg-memory-item ${selectedId === m.id ? 'selected' : ''}" data-id="${m.id}">
        <div class="pg-memory-title">${escapeHtml(m.title)}</div>
        <div class="pg-memory-meta">
          <span class="pg-memory-cat">${escapeHtml(m.category)}</span>
          <span>${escapeHtml(m.time)}</span>
        </div>
      </div>
    `).join('');

    memoryList.querySelectorAll('.pg-memory-item').forEach(item => {
      item.addEventListener('click', () => {
        selectedId = item.dataset.id;
        document.querySelectorAll('.pg-memory-item').forEach(i => i.classList.remove('selected'));
        item.classList.add('selected');
        const mem = DEMO_MEMORIES.find(m => m.id === selectedId);
        if (mem) showResult([mem]);
      });
    });
  }

  function filterByCategory(cat) {
    currentCategory = cat;
    return cat === 'all' ? DEMO_MEMORIES : DEMO_MEMORIES.filter(m => m.category === cat);
  }

  function search(query) {
    if (!query.trim()) {
      showEmpty();
      return;
    }

    const q = query.toLowerCase();
    const results = filterByCategory(currentCategory).filter(m =>
      m.title.toLowerCase().includes(q) ||
      m.content.toLowerCase().includes(q) ||
      m.tags.some(t => t.toLowerCase().includes(q))
    ).map(m => ({
      ...m,
      relevance: computeRelevance(query, m)
    })).sort((a, b) => b.relevance - a.relevance);

    showResult(results);
  }

  function computeRelevance(query, mem) {
    const q = query.toLowerCase();
    let score = 0;
    if (mem.title.toLowerCase().includes(q)) score += 0.5;
    if (mem.content.toLowerCase().includes(q)) score += 0.3;
    if (mem.tags.some(t => t.toLowerCase().includes(q))) score += 0.2;
    if (mem.importance === 'high') score += 0.1;
    return Math.min(score + Math.random() * 0.1, 0.99);
  }

  function showResult(results) {
    if (!results.length) {
      searchResults.innerHTML = `
        <div class="pg-empty">
          <div class="empty-icon">📭</div>
          <p>没有找到相关记忆</p>
          <span>试试其他关键词</span>
        </div>
      `;
      return;
    }

    searchResults.innerHTML = `<p style="font-size:0.85rem;color:var(--text-tertiary);margin-bottom:1rem;">找到 ${results.length} 条相关记忆</p>` +
      results.map(m => `
        <div class="result-card" data-id="${m.id}">
          <div class="result-header">
            <span class="result-category">${escapeHtml(m.category)}</span>
            <span class="result-relevance">相关度 <strong>${(m.relevance || 0.85).toFixed(2)}</strong></span>
          </div>
          <div class="result-content">${escapeHtml(m.content)}</div>
          <div class="result-tags">
            ${m.tags.map(t => `<span class="result-tag">#${escapeHtml(t)}</span>`).join('')}
          </div>
        </div>
      `).join('');
  }

  function showEmpty() {
    searchResults.innerHTML = `
      <div class="pg-empty">
        <div class="empty-icon">🔍</div>
        <p>输入关键词开始搜索</p>
        <span>支持语义检索、模糊匹配、分类筛选</span>
      </div>
    `;
  }

  categoryBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      categoryBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const cat = btn.dataset.cat;
      const filtered = filterByCategory(cat);
      renderMemoryList(filtered);
      showEmpty();
    });
  });

  searchBtn?.addEventListener('click', () => search(searchInput.value));
  searchInput?.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') search(searchInput.value);
  });

  renderMemoryList(DEMO_MEMORIES);
}

function initKnowledgeGraph() {
  const canvas = document.getElementById('graphCanvas');
  if (!canvas) return;

  const ctx = canvas.getContext('2d');
  let width, height;

  const nodes = [
    { id: '中心', label: '记忆核心', x: 0, y: 0, vx: 0, vy: 0, color: '#00d4ff', size: 24, isCenter: true },
    { id: 'n1', label: '数据库', x: -80, y: -60, vx: 0, vy: 0, color: '#a855f7', size: 16 },
    { id: 'n2', label: 'Python', x: 80, y: -50, vx: 0, vy: 0, color: '#f472b6', size: 16 },
    { id: 'n3', label: '产品创意', x: 0, y: 80, vx: 0, vy: 0, color: '#f59e0b', size: 16 },
    { id: 'n4', label: '工作项目', x: -90, y: 40, vx: 0, vy: 0, color: '#3b82f6', size: 14 },
    { id: 'n5', label: '生活记录', x: 90, y: 50, vx: 0, vy: 0, color: '#10b981', size: 14 },
    { id: 'n6', label: '设计系统', x: -50, y: -100, vx: 0, vy: 0, color: '#a855f7', size: 12 },
    { id: 'n7', label: '技术债务', x: 50, y: 100, vx: 0, vy: 0, color: '#ef4444', size: 12 },
    { id: 'n8', label: '咖啡', x: 120, y: 0, vx: 0, vy: 0, color: '#10b981', size: 10 },
  ];

  const edges = [
    { from: '中心', to: 'n1' },
    { from: '中心', to: 'n2' },
    { from: '中心', to: 'n3' },
    { from: '中心', to: 'n4' },
    { from: '中心', to: 'n5' },
    { from: 'n1', to: 'n6' },
    { from: 'n1', to: 'n7' },
    { from: 'n4', to: 'n7' },
    { from: 'n5', to: 'n8' },
    { from: 'n2', to: 'n3' },
  ];

  function resize() {
    const container = canvas.parentElement;
    width = canvas.width = container.clientWidth;
    height = canvas.height = container.clientHeight;
    nodes.forEach(n => {
      if (!n.isCenter) return;
      n.x = width / 2;
      n.y = height / 2;
    });
  }

  function getNode(id) {
    return nodes.find(n => n.id === id);
  }

  function simulate() {
    nodes.forEach(node => {
      if (node.isCenter) {
        node.vx *= 0.9;
        node.vy *= 0.9;
        return;
      }

      let fx = 0, fy = 0;

      nodes.forEach(other => {
        if (other.id === node.id) return;
        const dx = node.x - other.x;
        const dy = node.y - other.y;
        const dist = Math.sqrt(dx * dx + dy * dy) || 1;
        const force = 500 / (dist * dist);
        fx += (dx / dist) * force;
        fy += (dy / dist) * force;
      });

      edges.forEach(edge => {
        let other = null;
        if (edge.from === node.id) other = getNode(edge.to);
        else if (edge.to === node.id) other = getNode(edge.from);
        if (!other) return;

        const dx = other.x - node.x;
        const dy = other.y - node.y;
        const dist = Math.sqrt(dx * dx + dy * dy) || 1;
        const targetDist = 80;
        const force = (dist - targetDist) * 0.02;
        fx += (dx / dist) * force;
        fy += (dy / dist) * force;
      });

      const centerX = width / 2;
      const centerY = height / 2;
      fx += (centerX - node.x) * 0.001;
      fy += (centerY - node.y) * 0.001;

      node.vx = (node.vx + fx) * 0.9;
      node.vy = (node.vy + fy) * 0.9;
    });

    nodes.forEach(node => {
      node.x += node.vx;
      node.y += node.vy;
    });
  }

  function draw() {
    ctx.clearRect(0, 0, width, height);

    edges.forEach(edge => {
      const from = getNode(edge.from);
      const to = getNode(edge.to);
      if (!from || !to) return;

      const gradient = ctx.createLinearGradient(from.x, from.y, to.x, to.y);
      gradient.addColorStop(0, from.color + '40');
      gradient.addColorStop(1, to.color + '40');

      ctx.beginPath();
      ctx.moveTo(from.x, from.y);
      ctx.lineTo(to.x, to.y);
      ctx.strokeStyle = gradient;
      ctx.lineWidth = 1;
      ctx.stroke();
    });

    nodes.forEach(node => {
      ctx.beginPath();
      ctx.arc(node.x, node.y, node.size + 4, 0, Math.PI * 2);
      ctx.fillStyle = node.color + '20';
      ctx.fill();

      ctx.beginPath();
      ctx.arc(node.x, node.y, node.size, 0, Math.PI * 2);
      const gradient = ctx.createRadialGradient(node.x - 3, node.y - 3, 0, node.x, node.y, node.size);
      gradient.addColorStop(0, node.color);
      gradient.addColorStop(1, node.color + 'aa');
      ctx.fillStyle = gradient;
      ctx.fill();

      ctx.font = '11px Inter, sans-serif';
      ctx.fillStyle = 'rgba(255,255,255,0.7)';
      ctx.textAlign = 'center';
      ctx.fillText(node.label, node.x, node.y + node.size + 14);
    });
  }

  function animate() {
    simulate();
    draw();
    requestAnimationFrame(animate);
  }

  resize();
  animate();
  window.addEventListener('resize', resize);
}

function initNavScroll() {
  const nav = document.querySelector('.nav');
  if (!nav) return;

  let lastScroll = 0;
  window.addEventListener('scroll', () => {
    const currentScroll = window.pageYOffset;
    if (currentScroll > 100) {
      nav.style.background = 'rgba(10, 10, 15, 0.9)';
      nav.style.boxShadow = '0 4px 20px rgba(0,0,0,0.3)';
    } else {
      nav.style.background = 'rgba(10, 10, 15, 0.7)';
      nav.style.boxShadow = 'none';
    }
    lastScroll = currentScroll;
  });
}
