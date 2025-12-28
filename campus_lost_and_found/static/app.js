// ===== API 和状态管理 =====
const API_BASE = '';
let currentFilter = 'all';
let authToken = localStorage.getItem('token');
let currentUser = null;
let uploadedImagePath = null;
let aiDescription = null;

// ===== 工具函数 =====
function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(() => {
        toast.style.opacity = '0';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

async function apiRequest(endpoint, options = {}) {
    const headers = { 'Content-Type': 'application/json', ...options.headers };
    if (authToken) {
        headers['Authorization'] = `Bearer ${authToken}`;
    }

    try {
        const response = await fetch(`${API_BASE}${endpoint}`, { ...options, headers });
        if (response.status === 401) {
            logout();
            showToast('登录已过期，请重新登录', 'error');
            throw new Error('未授权');
        }
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'API 请求失败');
        }
        return await response.json();
    } catch (error) {
        console.error('API Error:', error);
        throw error;
    }
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function getStatusText(status) {
    const map = { 'OPEN': '待匹配', 'MATCHING': '匹配中', 'NEGOTIATING': '协商中', 'MATCHED': '已匹配', 'CLOSED': '已关闭' };
    return map[status] || status;
}

// ===== 认证相关 =====
function showAuthModal() {
    document.getElementById('auth-modal').style.display = 'flex';
}

function closeAuthModal() {
    document.getElementById('auth-modal').style.display = 'none';
}

function switchAuthTab(tab) {
    document.querySelectorAll('.auth-tab').forEach(t => t.classList.remove('active'));
    document.querySelector(`.auth-tab[onclick*="${tab}"]`).classList.add('active');
    document.getElementById('login-form').style.display = tab === 'login' ? 'block' : 'none';
    document.getElementById('register-form').style.display = tab === 'register' ? 'block' : 'none';
}

async function login(username, password) {
    try {
        const result = await apiRequest('/auth/login/json', {
            method: 'POST',
            body: JSON.stringify({ username, password })
        });
        authToken = result.access_token;
        localStorage.setItem('token', authToken);
        closeAuthModal();
        await loadCurrentUser();
        showToast('登录成功！', 'success');
    } catch (error) {
        showToast(`登录失败: ${error.message}`, 'error');
    }
}

async function register(data) {
    try {
        await apiRequest('/auth/register', {
            method: 'POST',
            body: JSON.stringify(data)
        });
        showToast('注册成功，请登录', 'success');
        switchAuthTab('login');
    } catch (error) {
        showToast(`注册失败: ${error.message}`, 'error');
    }
}

function logout() {
    authToken = null;
    currentUser = null;
    localStorage.removeItem('token');
    updateNavUser();
    showToast('已退出登录', 'info');
}

async function loadCurrentUser() {
    if (!authToken) return;
    try {
        currentUser = await apiRequest('/auth/me');
        updateNavUser();
    } catch (error) {
        logout();
    }
}

function updateNavUser() {
    const container = document.getElementById('nav-user');
    if (currentUser) {
        container.innerHTML = `
            <span class="user-name">👤 ${escapeHtml(currentUser.name)}</span>
            <button class="logout-btn" onclick="logout()">退出</button>
        `;
    } else {
        container.innerHTML = `<button class="login-btn" onclick="showAuthModal()">登录 / 注册</button>`;
    }
}

// ===== 导航 =====
document.querySelectorAll('.nav-link').forEach(link => {
    link.addEventListener('click', (e) => {
        e.preventDefault();
        const view = e.target.dataset.view || e.target.closest('.nav-link').dataset.view;

        // 检查是否需要登录
        if (['post', 'my-items', 'notifications', 'match-progress'].includes(view) && !authToken) {
            showAuthModal();
            return;
        }

        document.querySelectorAll('.nav-link').forEach(l => l.classList.remove('active'));
        e.target.closest('.nav-link').classList.add('active');
        document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
        document.getElementById(`${view}-view`).classList.add('active');

        if (view === 'home') loadItems();
        if (view === 'my-items') loadMyItems();
        if (view === 'notifications') loadNotifications();
        if (view === 'match-progress') loadMatchProgress();
    });
});

// ===== 筛选标签 =====
document.querySelectorAll('.filter-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
        document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
        e.target.classList.add('active');
        currentFilter = e.target.dataset.filter;
        loadItems();
    });
});

// ===== 加载物品列表 =====
async function loadItems() {
    const container = document.getElementById('items-container');
    container.innerHTML = '<div class="empty-state"><div class="icon">⏳</div><p>加载中...</p></div>';

    try {
        const items = await apiRequest('/items/');
        let filtered = items;
        if (currentFilter !== 'all') {
            filtered = items.filter(item => item.type === currentFilter);
        }

        if (filtered.length === 0) {
            container.innerHTML = '<div class="empty-state"><div class="icon">📭</div><p>暂无物品信息</p></div>';
            return;
        }

        container.innerHTML = filtered.map(item => `
            <div class="item-card ${item.type.toLowerCase()}" onclick="showItemDetail(${item.id})">
                ${item.images && item.images[0] ? `<div class="item-image"><img src="${item.images[0]}" alt="${escapeHtml(item.title)}"></div>` : ''}
                <div class="item-header">
                    <span class="item-title">${escapeHtml(item.title)}</span>
                    <span class="item-badge ${item.type.toLowerCase()}">${item.type === 'LOST' ? '丢失' : '拾取'}</span>
                </div>
                <p class="item-desc">${escapeHtml(item.description)}</p>
                <div class="item-meta">
                    <span>📍 ${escapeHtml(item.location)}</span>
                    <span>📋 ${getStatusText(item.status)}</span>
                </div>
            </div>
        `).join('');
    } catch (error) {
        container.innerHTML = `<div class="empty-state"><div class="icon">❌</div><p>加载失败: ${error.message}</p></div>`;
    }
}

// ===== 加载我的物品 =====
async function loadMyItems() {
    const container = document.getElementById('my-items-container');
    container.innerHTML = '<div class="empty-state"><div class="icon">⏳</div><p>加载中...</p></div>';

    try {
        const items = await apiRequest('/items/my');

        if (items.length === 0) {
            container.innerHTML = '<div class="empty-state"><div class="icon">📭</div><p>您还没有发布过物品</p></div>';
            return;
        }

        container.innerHTML = items.map(item => `
            <div class="item-card ${item.type.toLowerCase()}">
                ${item.images && item.images[0] ? `<div class="item-image"><img src="${item.images[0]}" alt="${escapeHtml(item.title)}"></div>` : ''}
                <div class="item-header">
                    <span class="item-title">${escapeHtml(item.title)}</span>
                    <span class="item-badge ${item.type.toLowerCase()}">${item.type === 'LOST' ? '丢失' : '拾取'}</span>
                </div>
                <p class="item-desc">${escapeHtml(item.description)}</p>
                <div class="item-meta">
                    <span>📍 ${escapeHtml(item.location)}</span>
                    <span>📋 ${getStatusText(item.status)}</span>
                </div>
                ${item.type === 'LOST' && item.status === 'OPEN' ? `
                    <button class="action-btn small" onclick="triggerMatch(${item.id})">🔍 触发匹配</button>
                ` : ''}
                <div class="item-actions">
                    <button class="action-btn small" onclick="showEditModal(${item.id}, '${escapeHtml(item.title)}', '${escapeHtml(item.description).replace(/'/g, "\\'")}', '${escapeHtml(item.location)}')">✏️ 编辑</button>
                    <button class="action-btn small danger" onclick="deleteItem(${item.id})">🗑️ 删除</button>
                </div>
            </div>
        `).join('');
    } catch (error) {
        container.innerHTML = `<div class="empty-state"><div class="icon">❌</div><p>加载失败: ${error.message}</p></div>`;
    }
}

async function triggerMatch(itemId) {
    try {
        const result = await apiRequest(`/items/${itemId}/match`, { method: 'POST' });
        showToast(result.message, 'success');
    } catch (error) {
        showToast(`触发失败: ${error.message}`, 'error');
    }
}

async function deleteItem(itemId) {
    if (!confirm('确定要删除这个物品吗？')) return;

    try {
        const result = await apiRequest(`/items/${itemId}`, { method: 'DELETE' });
        showToast(result.message, 'success');
        loadMyItems();
    } catch (error) {
        showToast(`删除失败: ${error.message}`, 'error');
    }
}

// ===== 编辑物品 =====
function showEditModal(itemId, title, description, location) {
    document.getElementById('edit-item-id').value = itemId;
    document.getElementById('edit-title').value = title;
    document.getElementById('edit-description').value = description;
    document.getElementById('edit-location').value = location;
    document.getElementById('edit-item-modal').style.display = 'flex';
}

function closeEditModal() {
    document.getElementById('edit-item-modal').style.display = 'none';
}

document.getElementById('edit-item-form')?.addEventListener('submit', async (e) => {
    e.preventDefault();

    const itemId = document.getElementById('edit-item-id').value;
    const data = {
        title: document.getElementById('edit-title').value,
        description: document.getElementById('edit-description').value,
        location: document.getElementById('edit-location').value
    };

    try {
        const result = await apiRequest(`/items/${itemId}`, {
            method: 'PATCH',
            body: JSON.stringify(data)
        });
        showToast(result.message, 'success');
        closeEditModal();
        loadMyItems();
    } catch (error) {
        showToast(`修改失败: ${error.message}`, 'error');
    }
});

// ===== 加载通知 =====
async function loadNotifications() {
    const container = document.getElementById('notifications-container');
    container.innerHTML = '<div class="empty-state"><div class="icon">⏳</div><p>加载中...</p></div>';

    try {
        const notifications = await apiRequest('/notifications/');

        if (notifications.length === 0) {
            container.innerHTML = '<div class="empty-state"><div class="icon">🔔</div><p>暂无消息</p></div>';
            return;
        }

        container.innerHTML = notifications.map(n => `
            <div class="notification-card ${n.is_read ? 'read' : 'unread'}" onclick="handleNotification(${n.id}, ${n.session_id})">
                <div class="notif-icon">${getNotifIcon(n.type)}</div>
                <div class="notif-content">
                    <div class="notif-title">${escapeHtml(n.title)}</div>
                    <div class="notif-message">${escapeHtml(n.message || '')}</div>
                    <div class="notif-time">${formatTime(n.created_at)}</div>
                </div>
            </div>
        `).join('');

        updateNotifBadge(notifications.filter(n => !n.is_read).length);
    } catch (error) {
        container.innerHTML = `<div class="empty-state"><div class="icon">❌</div><p>加载失败: ${error.message}</p></div>`;
    }
}

function getNotifIcon(type) {
    const icons = { 'MATCH_FOUND': '🎉', 'CONFIRM_REQUEST': '❓', 'SCHEDULE': '📅', 'NO_MATCH': '😢', 'NEGOTIATION_UPDATE': '💬' };
    return icons[type] || '🔔';
}

function formatTime(isoString) {
    if (!isoString) return '';
    const date = new Date(isoString);
    return date.toLocaleString('zh-CN');
}

function updateNotifBadge(count) {
    const badge = document.getElementById('notif-badge');
    if (count > 0) {
        badge.textContent = count;
        badge.style.display = 'inline';
    } else {
        badge.style.display = 'none';
    }
}

async function handleNotification(notifId, sessionId) {
    // 标记已读
    await apiRequest(`/notifications/${notifId}/read`, { method: 'POST' });

    if (sessionId) {
        // 显示协商详情
        showNegotiationDetail(sessionId);
    }

    loadNotifications();
}

// ===== 实时轮询协商进度 =====
let currentSessionId = null;
let negotiationPollInterval = null;

async function showNegotiationDetail(sessionId) {
    // 停止之前的轮询
    if (negotiationPollInterval) {
        clearInterval(negotiationPollInterval);
        negotiationPollInterval = null;
    }

    currentSessionId = sessionId;

    document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
    document.getElementById('negotiation-detail-view').classList.add('active');

    const container = document.getElementById('negotiation-detail');
    container.innerHTML = '<div class="empty-state"><div class="icon">⏳</div><p>加载中...</p></div>';

    try {
        const session = await apiRequest(`/negotiations/${sessionId}`);

        container.innerHTML = `
            <div class="session-card">
                <div class="session-header">
                    <span>会话 #${session.id}</span>
                    <span class="session-status ${session.status.toLowerCase()}">${session.status}</span>
                </div>
                
                <div class="match-info">
                    <div class="match-item clickable" onclick="showItemDetail(${session.lost_item?.id})">
                        <h4>😢 丢失物品 <span class="click-hint">点击查看详情</span></h4>
                        <p><strong>${escapeHtml(session.lost_item?.title)}</strong></p>
                        <p>${escapeHtml(session.lost_item?.description)}</p>
                    </div>
                    <div class="match-arrow">↔️</div>
                    <div class="match-item clickable" onclick="showItemDetail(${session.found_item?.id})">
                        <h4>🎉 拾取物品 <span class="click-hint">点击查看详情</span></h4>
                        <p><strong>${escapeHtml(session.found_item?.title)}</strong></p>
                        <p>${escapeHtml(session.found_item?.description)}</p>
                    </div>
                </div>
                
                <div class="chat-log">
                    <h4>💬 协商记录</h4>
                    ${(session.chat_log || []).map(msg => `
                        <div class="chat-message ${msg.sender === 'Seeker' ? 'seeker' : msg.sender === 'Finder' ? 'finder' : 'system'}">
                            <div class="message-sender">${msg.sender === 'Seeker' ? '失主代理' : msg.sender === 'Finder' ? '拾主代理' : '系统'}</div>
                            <div class="message-text">${escapeHtml(msg.content)}</div>
                        </div>
                    `).join('')}
                </div>
                
                ${session.status === 'PENDING_CONFIRM' ? `
                    <div class="confirm-section">
                        <h4>这是您丢失的物品吗？</h4>
                        <div class="confirm-actions">
                            <button class="confirm-btn accept" onclick="confirmItem(${sessionId}, true)">✅ 是的，这是我的</button>
                            <button class="confirm-btn reject" onclick="confirmItem(${sessionId}, false)">❌ 不是我的</button>
                        </div>
                    </div>
                ` : ''}
                
                ${['FAILED', 'REJECTED'].includes(session.status) ? `
                    <div class="force-match-section">
                        <h4>⚠️ 协商失败</h4>
                        <p>如果您确认这就是您丢失的物品，可以强制标记为匹配成功。</p>
                        <button class="action-btn" onclick="forceMatch(${sessionId})">🔄 确认是我的物品，强制匹配</button>
                    </div>
                ` : ''}
                
                ${session.status === 'CONFIRMED' ? `
                    ${isFinderView(session) ? `
                        <div class="schedule-section">
                            <h4>📅 发起归还约定</h4>
                            ${getLastRejectedSchedule(session)}
                            <form onsubmit="submitSchedule(event, ${sessionId})">
                                <div class="form-group">
                                    <label>时间</label>
                                    <input type="datetime-local" name="time" required>
                                </div>
                                <div class="form-group">
                                    <label>地点</label>
                                    <input type="text" name="location" placeholder="例如：图书馆门口" required>
                                </div>
                                <div class="form-group">
                                    <label>备注</label>
                                    <textarea name="notes" placeholder="其他说明..."></textarea>
                                </div>
                                <button type="submit" class="submit-btn">发起约定</button>
                            </form>
                        </div>
                    ` : `
                        <div class="waiting-section">
                            <h4>⏳ 等待拾主发起约定</h4>
                            <p>物品已确认匹配，请等待拾主发起归还时间地点约定。</p>
                        </div>
                    `}
                ` : ''}
                
                ${session.status === 'SCHEDULE_PENDING' ? `
                    <div class="schedule-pending-section">
                        <h4>📋 约定详情</h4>
                        ${session.schedule ? `
                            <div class="schedule-detail">
                                <p><strong>时间：</strong>${formatTime(session.schedule.proposed_time)}</p>
                                <p><strong>地点：</strong>${escapeHtml(session.schedule.proposed_location)}</p>
                                ${session.schedule.notes ? `<p><strong>备注：</strong>${escapeHtml(session.schedule.notes)}</p>` : ''}
                            </div>
                        ` : ''}
                        
                        ${isFinderView(session) ? `
                            <div class="waiting-section">
                                <p>⏳ 等待失主确认约定...</p>
                            </div>
                        ` : `
                            <div class="approve-section">
                                <p>请确认是否同意此约定：</p>
                                <div class="approve-actions">
                                    <button class="confirm-btn accept" onclick="approveSchedule(${sessionId})">✅ 同意约定</button>
                                    <button class="confirm-btn reject" onclick="showRejectForm(${sessionId})">❌ 回绝约定</button>
                                </div>
                                <div id="reject-form-${sessionId}" style="display:none; margin-top: 1rem;">
                                    <div class="form-group">
                                        <label>回绝理由（必填）</label>
                                        <textarea id="reject-reason-${sessionId}" placeholder="请说明回绝原因..." required></textarea>
                                    </div>
                                    <button class="action-btn" onclick="rejectSchedule(${sessionId})">确认回绝</button>
                                </div>
                            </div>
                        `}
                    </div>
                ` : ''}
                
                ${session.status === 'WAITING_RETURN' ? `
                    <div class="return-section">
                        <h4>⏳ 等待归还</h4>
                        ${session.schedule ? `
                            <div class="schedule-detail">
                                <p><strong>约定时间：</strong>${formatTime(session.schedule.proposed_time)}</p>
                                <p><strong>约定地点：</strong>${escapeHtml(session.schedule.proposed_location)}</p>
                            </div>
                        ` : ''}
                        <p>请按约定时间地点线下交接物品。交接后请选择归还结果：</p>
                        <div class="return-actions">
                            <button class="confirm-btn accept" onclick="confirmReturnStatus(${sessionId}, true)">✅ 已成功归还</button>
                            <button class="confirm-btn reject" onclick="confirmReturnStatus(${sessionId}, false)">❌ 归还失败（不是同一物品）</button>
                        </div>
                        <p class="hint">失主: ${session.seeker_confirmed === true ? '✅已确认' : session.seeker_confirmed === false ? '❌已拒绝' : '⏳待确认'} | 拾主: ${session.finder_confirmed === true ? '✅已确认' : session.finder_confirmed === false ? '❌已拒绝' : '⏳待确认'}</p>
                    </div>
                ` : ''}
                
                ${session.status === 'RETURNED' ? `
                    <div class="success-section">
                        <h4>🎉 归还成功！</h4>
                        <p>物品已成功归还，双方确认完毕。感谢使用！</p>
                    </div>
                ` : ''}
                
                ${session.status === 'RETURN_FAILED' ? `
                    <div class="failed-section">
                        <h4>❌ 归还失败</h4>
                        <p>线下确认不匹配，物品已恢复可匹配状态，系统将继续为您搜索。</p>
                    </div>
                ` : ''}
            </div>
        `;

        // 如果协商进行中，启动轮询
        if (session.status === 'ACTIVE') {
            negotiationPollInterval = setInterval(async () => {
                try {
                    const updated = await apiRequest(`/negotiations/${sessionId}`);
                    updateNegotiationChat(updated);

                    // 如果协商完成，停止轮询
                    if (updated.status !== 'ACTIVE') {
                        clearInterval(negotiationPollInterval);
                        negotiationPollInterval = null;
                        showNegotiationDetail(sessionId); // 重新加载完整页面
                    }
                } catch (e) {
                    console.error('轮询失败', e);
                }
            }, 2000); // 每 2 秒刷新
        }
    } catch (error) {
        container.innerHTML = `<div class="empty-state"><div class="icon">❌</div><p>加载失败: ${error.message}</p></div>`;
    }
}

// 只更新聊天记录部分，避免整页刷新
function updateNegotiationChat(session) {
    const chatLog = document.querySelector('.chat-log');
    if (!chatLog) return;

    chatLog.innerHTML = `
        <h4>💬 协商记录 <span style="color: var(--accent); font-size: 0.8rem;">(实时更新中...)</span></h4>
        ${(session.chat_log || []).map(msg => `
            <div class="chat-message ${msg.sender === 'Seeker' ? 'seeker' : 'finder'}">
                <div class="message-sender">${msg.sender === 'Seeker' ? '失主代理' : '拾主代理'}</div>
                <div class="message-text">${escapeHtml(msg.content)}</div>
            </div>
        `).join('')}
    `;

    // 滚动到底部
    chatLog.scrollTop = chatLog.scrollHeight;
}

async function confirmItem(sessionId, isMyItem) {
    try {
        const result = await apiRequest(`/negotiations/${sessionId}/confirm?is_my_item=${isMyItem}`, { method: 'POST' });
        showToast(result.message, 'success');
        showNegotiationDetail(sessionId);
    } catch (error) {
        showToast(`操作失败: ${error.message}`, 'error');
    }
}

async function forceMatch(sessionId) {
    if (!confirm('确认这是您丢失的物品吗？这将强制标记为匹配成功。')) return;

    try {
        const result = await apiRequest(`/negotiations/${sessionId}/force-match`, { method: 'POST' });
        showToast(result.message, 'success');
        showNegotiationDetail(sessionId);
    } catch (error) {
        showToast(`操作失败: ${error.message}`, 'error');
    }
}

async function submitSchedule(e, sessionId) {
    e.preventDefault();
    const form = e.target;
    const data = {
        proposed_time: form.time.value,
        proposed_location: form.location.value,
        notes: form.notes.value
    };

    try {
        const result = await apiRequest(`/negotiations/${sessionId}/schedule`, {
            method: 'POST',
            body: JSON.stringify(data)
        });
        showToast(result.message, 'success');
        showNegotiationDetail(sessionId);
    } catch (error) {
        showToast(`提交失败: ${error.message}`, 'error');
    }
}

// 判断当前用户是否是拾主
function isFinderView(session) {
    const userId = getCurrentUserId();
    if (!userId || !session.found_item) return false;
    // 转换为数字比较避免类型问题
    return Number(session.found_item.owner_id) === Number(userId);
}

// 判断当前用户是否是失主
function isSeekerView(session) {
    const userId = getCurrentUserId();
    if (!userId || !session.lost_item) return false;
    return Number(session.lost_item.owner_id) === Number(userId);
}

// 获取当前登录用户 ID
function getCurrentUserId() {
    const token = localStorage.getItem('token');
    if (!token) return null;
    try {
        const parts = token.split('.');
        if (parts.length !== 3) return null;
        const payload = JSON.parse(atob(parts[1]));
        return payload.user_id;
    } catch (e) {
        console.error('解析 token 失败:', e);
        return null;
    }
}

// 显示上次被回绝的约定信息
function getLastRejectedSchedule(session) {
    if (session.schedule && session.schedule.status === 'REJECTED' && session.schedule.reject_reason) {
        return `<div class="rejected-schedule">
            <p>⚠️ 上次约定被回绝</p>
            <p><strong>回绝理由：</strong>${escapeHtml(session.schedule.reject_reason)}</p>
        </div>`;
    }
    return '';
}

// 同意约定
async function approveSchedule(sessionId) {
    try {
        const result = await apiRequest(`/negotiations/${sessionId}/schedule/approve`, { method: 'POST' });
        showToast(result.message, 'success');
        showNegotiationDetail(sessionId);
    } catch (error) {
        showToast(`操作失败: ${error.message}`, 'error');
    }
}

// 显示回绝表单
function showRejectForm(sessionId) {
    document.getElementById(`reject-form-${sessionId}`).style.display = 'block';
}

// 回绝约定
async function rejectSchedule(sessionId) {
    const reason = document.getElementById(`reject-reason-${sessionId}`).value.trim();
    if (!reason) {
        showToast('请填写回绝理由', 'error');
        return;
    }

    try {
        const result = await apiRequest(`/negotiations/${sessionId}/schedule/reject`, {
            method: 'POST',
            body: JSON.stringify({ reason })
        });
        showToast(result.message, 'success');
        showNegotiationDetail(sessionId);
    } catch (error) {
        showToast(`操作失败: ${error.message}`, 'error');
    }
}

// 确认归还状态
async function confirmReturnStatus(sessionId, isReturned) {
    const msg = isReturned ? '确认物品已成功归还吗？' : '确认归还失败吗？物品将恢复可匹配状态。';
    if (!confirm(msg)) return;

    try {
        const result = await apiRequest(`/negotiations/${sessionId}/confirm-return?is_returned=${isReturned}`, { method: 'POST' });
        showToast(result.message, 'success');
        showNegotiationDetail(sessionId);
    } catch (error) {
        showToast(`操作失败: ${error.message}`, 'error');
    }
}

// ===== 图片上传 =====
document.getElementById('image-input').addEventListener('change', async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    // 显示预览
    const reader = new FileReader();
    reader.onload = (e) => {
        document.getElementById('preview-image').src = e.target.result;
        document.querySelector('.upload-placeholder').style.display = 'none';
        document.getElementById('upload-preview').style.display = 'block';
    };
    reader.readAsDataURL(file);

    // 上传并识别
    document.getElementById('ai-analysis').style.display = 'block';
    document.getElementById('ai-loading').style.display = 'flex';
    document.getElementById('ai-result').style.display = 'none';

    const formData = new FormData();
    formData.append('file', file);
    formData.append('item_type', document.querySelector('input[name="type"]:checked').value === 'LOST' ? '丢失物品' : '拾取物品');

    try {
        const response = await fetch('/images/analyze', { method: 'POST', body: formData });
        const result = await response.json();

        uploadedImagePath = result.path;
        aiDescription = result.ai_description;

        document.getElementById('ai-loading').style.display = 'none';
        document.getElementById('ai-result').style.display = 'block';
        document.getElementById('ai-description-text').textContent = aiDescription;
        document.getElementById('image-path').value = uploadedImagePath;
    } catch (error) {
        document.getElementById('ai-loading').style.display = 'none';
        showToast(`图片识别失败: ${error.message}`, 'error');
    }
});

function removeImage() {
    document.getElementById('image-input').value = '';
    document.querySelector('.upload-placeholder').style.display = 'flex';
    document.getElementById('upload-preview').style.display = 'none';
    document.getElementById('ai-analysis').style.display = 'none';
    uploadedImagePath = null;
    aiDescription = null;
}

function useAiDescription() {
    if (aiDescription) {
        document.getElementById('description').value = aiDescription;
        document.getElementById('ai-description').value = aiDescription;
        showToast('已应用 AI 描述', 'success');
    }
}

// ===== 表单提交 =====
document.getElementById('login-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const form = e.target;
    await login(form.username.value, form.password.value);
});

document.getElementById('register-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const form = e.target;
    await register({
        username: form.username.value,
        password: form.password.value,
        name: form.name.value,
        contact_info: form.contact_info.value
    });
});

document.getElementById('post-form').addEventListener('submit', async (e) => {
    e.preventDefault();

    if (!authToken) {
        showAuthModal();
        return;
    }

    const form = e.target;
    const data = {
        title: form.title.value,
        description: form.description.value,
        type: form.type.value,
        location: form.location.value,
        ai_description: form.ai_description.value || null
    };

    // 构建请求 URL（包含图片路径）
    let url = '/items/';
    if (uploadedImagePath) {
        url += `?image_paths=${encodeURIComponent(JSON.stringify([uploadedImagePath]))}`;
    }

    try {
        const result = await apiRequest(url, {
            method: 'POST',
            body: JSON.stringify(data)
        });

        showToast('物品发布成功！', 'success');
        form.reset();
        removeImage();

        // 跳转到首页
        document.querySelector('.nav-link[data-view="home"]').click();
    } catch (error) {
        showToast(`发布失败: ${error.message}`, 'error');
    }
});

// ===== 匹配进度 =====
let currentProgressFilter = 'all';

async function loadMatchProgress(filter = null) {
    if (filter) currentProgressFilter = filter;

    const container = document.getElementById('sessions-container');
    container.innerHTML = '<div class="empty-state"><div class="icon">⏳</div><p>加载中...</p></div>';

    try {
        const sessions = await apiRequest('/negotiations/');

        let filtered = sessions;
        if (currentProgressFilter === 'active') {
            filtered = sessions.filter(s => ['ACTIVE', 'PENDING_CONFIRM'].includes(s.status));
        } else if (currentProgressFilter === 'success') {
            filtered = sessions.filter(s => ['SUCCESS', 'CONFIRMED'].includes(s.status));
        }

        if (filtered.length === 0) {
            container.innerHTML = '<div class="empty-state"><div class="icon">📭</div><p>暂无匹配记录</p></div>';
            return;
        }

        container.innerHTML = filtered.map(session => `
            <div class="session-card" onclick="showNegotiationDetail(${session.id})">
                <div class="session-header">
                    <span class="session-id">会话 #${session.id}</span>
                    <span class="session-status ${session.status.toLowerCase()}">${getSessionStatusText(session.status)}</span>
                </div>
                <div class="session-items">
                    <div class="session-item lost">
                        <span class="item-icon">😢</span>
                        <span>${escapeHtml(session.lost_item?.title || '未知物品')}</span>
                    </div>
                    <div class="match-arrow">↔️</div>
                    <div class="session-item found">
                        <span class="item-icon">🎉</span>
                        <span>${escapeHtml(session.found_item?.title || '未知物品')}</span>
                    </div>
                </div>
                <div class="session-meta">
                    <span>匹配度: ${(session.match_score * 100).toFixed(0)}%</span>
                    <span>${formatTime(session.created_at)}</span>
                </div>
            </div>
        `).join('');
    } catch (error) {
        container.innerHTML = `<div class="empty-state"><div class="icon">❌</div><p>加载失败: ${error.message}</p></div>`;
    }
}

function loadProgressTab(filter) {
    currentProgressFilter = filter;

    document.querySelectorAll('.progress-tab').forEach(t => t.classList.remove('active'));
    document.querySelector(`.progress-tab[onclick*="${filter}"]`).classList.add('active');

    loadMatchProgress(filter);
}

function getSessionStatusText(status) {
    const map = {
        'ACTIVE': '协商中',
        'SUCCESS': '匹配成功',
        'FAILED': '匹配失败',
        'PENDING_CONFIRM': '等待确认',
        'CONFIRMED': '已确认',
        'REJECTED': '已拒绝',
        'SCHEDULE_PENDING': '约定待确认',
        'WAITING_RETURN': '等待归还',
        'RETURNED': '已归还',
        'RETURN_FAILED': '归还失败'
    };
    return map[status] || status;
}

// ===== 物品详情模态框 =====
async function showItemDetail(itemId) {
    const modal = document.getElementById('item-detail-modal');
    const container = document.getElementById('item-detail-content');

    modal.style.display = 'flex';
    container.innerHTML = '<div class="empty-state" style="padding:2rem;"><div class="icon">⏳</div><p>加载中...</p></div>';

    try {
        const item = await apiRequest(`/items/${itemId}`);

        container.innerHTML = `
            <div class="item-detail">
                ${item.images && item.images[0] ? `
                    <div class="detail-image">
                        <img src="${item.images[0]}" alt="${escapeHtml(item.title)}">
                    </div>
                ` : ''}
                <div class="detail-info">
                    <div class="detail-header">
                        <h3>${escapeHtml(item.title)}</h3>
                        <span class="item-badge ${item.type.toLowerCase()}">${item.type === 'LOST' ? '丢失' : '拾取'}</span>
                    </div>
                    <div class="detail-section">
                        <h4>📝 用户描述</h4>
                        <p>${escapeHtml(item.description)}</p>
                    </div>
                    ${item.ai_description ? `
                        <div class="detail-section">
                            <h4>🤖 AI 识别</h4>
                            <p>${escapeHtml(item.ai_description)}</p>
                        </div>
                    ` : ''}
                    <div class="detail-section">
                        <h4>📍 地点</h4>
                        <p>${escapeHtml(item.location)}</p>
                    </div>
                    <div class="detail-section">
                        <h4>👤 发布者</h4>
                        <p>${escapeHtml(item.owner?.name || '未知')}</p>
                    </div>
                    <div class="detail-section">
                        <h4>📋 状态</h4>
                        <p>${getStatusText(item.status)}</p>
                    </div>
                </div>
            </div>
        `;
    } catch (error) {
        container.innerHTML = `<div class="empty-state"><div class="icon">❌</div><p>加载失败: ${error.message}</p></div>`;
    }
}

function closeItemModal() {
    document.getElementById('item-detail-modal').style.display = 'none';
}

// ===== 返回匹配进度 =====
function goBackToProgress() {
    document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
    document.getElementById('match-progress-view').classList.add('active');

    document.querySelectorAll('.nav-link').forEach(l => l.classList.remove('active'));
    document.querySelector('.nav-link[data-view="match-progress"]').classList.add('active');

    loadMatchProgress();
}

// ===== 初始化 =====
document.addEventListener('DOMContentLoaded', async () => {
    await loadCurrentUser();
    loadItems();

    // 定期刷新通知
    if (authToken) {
        setInterval(async () => {
            try {
                const notifs = await apiRequest('/notifications/?unread_only=true');
                updateNotifBadge(notifs.length);
            } catch { }
        }, 30000);
    }
});
