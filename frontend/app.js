/**
 * 前端逻辑 — 双栏交互控制
 *
 * 左栏 (DB Style): 提交文本 → 显示保存结果
 * 右栏 (Blackboard Style): 提交文本 → 轮询状态 → 逐步展示处理过程
 */

const DB_API = '/api/db';
const BB_API = '/api/blackboard';

// ==================== DB Style ====================

async function submitDB() {
    const input = document.getElementById('db-input');
    const submitBtn = document.getElementById('db-submit');
    const content = input.value.trim();

    if (!content) return;

    submitBtn.disabled = true;
    submitBtn.textContent = '保存中...';

    try {
        // POST 到 db_service
        const res = await fetch(`${DB_API}/analyze`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ content }),
        });
        const data = await res.json();

        // 显示保存结果
        showDBResult(data);
        // 刷新历史记录
        loadDBHistory();
    } catch (err) {
        console.error('DB submit error:', err);
        alert('提交失败，请检查后端服务是否启动');
    } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = '提交到数据库';
    }
}

function showDBResult(record) {
    const container = document.getElementById('db-result');
    const content = document.getElementById('db-result-content');

    container.classList.remove('hidden');
    content.innerHTML = `
        <div class="fade-in">
            <p><span class="text-gray-500">ID:</span> ${record.id}</p>
            <p class="mt-1"><span class="text-gray-500">内容:</span> ${escapeHtml(record.content)}</p>
            <p class="mt-1"><span class="text-gray-500">时间:</span> ${new Date(record.created_at).toLocaleString('zh-CN')}</p>
        </div>
    `;
}

async function loadDBHistory() {
    try {
        const res = await fetch(`${DB_API}/history`);
        const records = await res.json();

        const container = document.getElementById('db-history');
        const list = document.getElementById('db-history-list');

        if (records.length === 0) {
            container.classList.add('hidden');
            return;
        }

        container.classList.remove('hidden');
        list.innerHTML = records.slice(0, 5).map(r => `
            <div class="bg-gray-900 rounded p-3 text-xs border border-gray-700 fade-in">
                <p class="text-gray-400 truncate">${escapeHtml(r.content.substring(0, 60))}...</p>
                <p class="text-gray-600 mt-1">ID: ${r.id} | ${new Date(r.created_at).toLocaleString('zh-CN')}</p>
            </div>
        `).join('');
    } catch (err) {
        console.error('Load history error:', err);
    }
}

// ==================== Blackboard Style ====================

let pollingInterval = null;

async function submitBlackboard() {
    const input = document.getElementById('bb-input');
    const submitBtn = document.getElementById('bb-submit');
    const content = input.value.trim();

    if (!content) return;

    // 停止之前的轮询
    stopPolling();

    submitBtn.disabled = true;
    submitBtn.textContent = '提交中...';

    try {
        // POST 到 blackboard_service
        const res = await fetch(`${BB_API}/analyze`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ content }),
        });
        const data = await res.json();

        // 显示处理管线
        showBlackboardPipeline(data.task_id);
        // 开始轮询
        startPolling(data.task_id);
    } catch (err) {
        console.error('Blackboard submit error:', err);
        alert('提交失败，请检查后端服务是否启动');
    } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = '提交到黑板系统';
    }
}

function showBlackboardPipeline(taskId) {
    const pipeline = document.getElementById('bb-pipeline');
    const results = document.getElementById('bb-results');

    pipeline.classList.remove('hidden');
    results.innerHTML = '';

    // 重置所有阶段指示器
    resetStages();

    // 显示初始化阶段
    activateStage('init');
    addResultCard('init', '初始化', '黑板 entry 已创建，等待控制器调度...', 'gray');
}

function startPolling(taskId) {
    pollingInterval = setInterval(async () => {
        try {
            const res = await fetch(`${BB_API}/${taskId}`);
            const data = await res.json();
            updatePipeline(data);

            if (data.stage === 'completed' || data.stage === 'error') {
                stopPolling();
                document.getElementById('bb-submit').disabled = false;
            }
        } catch (err) {
            console.error('Polling error:', err);
        }
    }, 500);
}

function stopPolling() {
    if (pollingInterval) {
        clearInterval(pollingInterval);
        pollingInterval = null;
    }
}

function updatePipeline(data) {
    const results = document.getElementById('bb-results');
    results.innerHTML = '';

    // Stage 1: Init
    if (data.stage !== 'init') {
        activateStage('init');
        completeStage('init');
        addResultCard('init', '初始化', '黑板 entry 已创建，状态: init → keyword_done', 'green');
    }

    // Stage A: Keywords
    if (data.keywords) {
        activateStage('keyword');
        completeStage('keyword');
        addResultCard('keyword', '知识源A: 关键词提取', `提取到关键词: ${data.keywords.join('、')}`, 'green');
    } else if (data.stage === 'init') {
        activateStage('keyword');
        addResultCard('keyword', '知识源A: 关键词提取', '等待中... 控制器将在 stage == init 时激活', 'yellow');
    }

    // Stage B: Sentiment
    if (data.sentiment) {
        activateStage('sentiment');
        completeStage('sentiment');
        const sentimentText = { positive: '积极', negative: '消极', neutral: '中性' };
        const label = sentimentText[data.sentiment.label] || '未知';
        addResultCard('sentiment', '知识源B: 情感分析',
            `情感倾向: ${label} (置信度 ${data.sentiment.confidence})\n积极词: ${data.sentiment.positive} | 消极词: ${data.sentiment.negative}`,
            'green');
    } else if (data.stage === 'keyword_done') {
        activateStage('sentiment');
        addResultCard('sentiment', '知识源B: 情感分析', '等待中... 控制器将在 stage == keyword_done 时激活', 'yellow');
    }

    // Stage C: Summary
    if (data.summary) {
        activateStage('summary');
        completeStage('summary');
        addResultCard('summary', '知识源C: 总结归纳', data.summary, 'green');
    } else if (data.stage === 'sentiment_done') {
        activateStage('summary');
        addResultCard('summary', '知识源C: 总结归纳', '等待中... 控制器将在 stage == sentiment_done 时激活', 'yellow');
    }

    // Completed
    if (data.stage === 'completed') {
        addResultCard('done', '处理完成', '所有知识源执行完毕，黑板状态: completed', 'green');
    }

    // Error
    if (data.error) {
        addResultCard('error', '错误', `处理出错: ${data.error}`, 'red');
    }
}

function resetStages() {
    ['init', 'keyword', 'sentiment', 'summary'].forEach(stage => {
        const el = document.getElementById(`stage-${stage}`);
        el.className = 'stage-dot w-10 h-10 rounded-full bg-gray-600 flex items-center justify-center text-xs font-bold';
    });
    document.getElementById('progress-1').style.width = '0';
    document.getElementById('progress-2').style.width = '0';
    document.getElementById('progress-3').style.width = '0';
}

function activateStage(stage) {
    const el = document.getElementById(`stage-${stage}`);
    el.className = 'stage-dot w-10 h-10 rounded-full bg-emerald-500 flex items-center justify-center text-xs font-bold text-white stage-active';
}

function completeStage(stage) {
    const el = document.getElementById(`stage-${stage}`);
    el.className = 'stage-dot w-10 h-10 rounded-full bg-emerald-700 flex items-center justify-center text-xs font-bold text-white';

    const progressMap = { init: 'progress-1', keyword: 'progress-2', sentiment: 'progress-3' };
    if (progressMap[stage]) {
        document.getElementById(progressMap[stage]).style.width = '100%';
    }
}

function addResultCard(id, title, content, color) {
    const results = document.getElementById('bb-results');
    const colorClasses = {
        green: 'border-emerald-700 bg-emerald-900/30',
        yellow: 'border-yellow-700 bg-yellow-900/30',
        red: 'border-red-700 bg-red-900/30',
        gray: 'border-gray-700 bg-gray-900/30',
    };

    const card = document.createElement('div');
    card.className = `rounded-lg border p-4 fade-in ${colorClasses[color] || colorClasses.gray}`;
    card.innerHTML = `
        <h4 class="font-medium text-sm text-gray-200 mb-2">${title}</h4>
        <p class="text-sm text-gray-400 whitespace-pre-line">${escapeHtml(content)}</p>
    `;
    results.appendChild(card);
}

// ==================== Utilities ====================

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

// 页面加载时刷新 DB 历史记录
document.addEventListener('DOMContentLoaded', () => {
    loadDBHistory();
});
