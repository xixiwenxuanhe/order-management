// 全局变量
let ordersData = [];
let filteredOrders = [];
let currentDisplayPage = 1;
const ordersPerPage = 30;

// DOM 元素
const ordersList = document.getElementById('ordersList');
const totalOrdersEl = document.getElementById('totalOrders');
const totalPagesEl = document.getElementById('totalPages');
const totalAmountEl = document.getElementById('totalAmount');
const statusFilter = document.getElementById('statusFilter');
const searchInput = document.getElementById('searchInput');
const pageSelect = document.getElementById('pageSelect');
const prevBtn = document.getElementById('prevBtn');
const nextBtn = document.getElementById('nextBtn');
const pageInfo = document.getElementById('pageInfo');
const loading = document.getElementById('loading');

// 初始化应用
document.addEventListener('DOMContentLoaded', function() {
    loadOrdersData();
    setupEventListeners();
});

// 设置事件监听器
function setupEventListeners() {
    statusFilter.addEventListener('change', applyFilters);
    searchInput.addEventListener('input', debounce(applyFilters, 300));
    pageSelect.addEventListener('change', applyFilters);
    prevBtn.addEventListener('click', () => changePage(-1));
    nextBtn.addEventListener('click', () => changePage(1));
}

// 防抖函数
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// 加载订单数据
async function loadOrdersData() {
    try {
        showLoading(true);
        const response = await fetch('optimized_orders.json');
        const data = await response.json();
        
        // 解析优化后的数据结构
        ordersData = data;
        
        console.log('加载的订单数据:', ordersData);
        
        populateFilterOptions();
        filteredOrders = [...ordersData];
        updateStats();
        displayOrders();
        updatePagination();
        
    } catch (error) {
        console.error('加载数据失败:', error);
        ordersList.innerHTML = '<div class="error">数据加载失败，请检查 optimized_orders.json 文件是否存在</div>';
    } finally {
        showLoading(false);
    }
}

// 显示/隐藏加载状态
function showLoading(show) {
    loading.style.display = show ? 'flex' : 'none';
}

// 填充过滤选项
function populateFilterOptions() {
    // 状态选项
    const statuses = [...new Set(ordersData.map(order => order.orderInfo?.status?.name).filter(Boolean))];
    statuses.forEach(status => {
        const option = document.createElement('option');
        option.value = status;
        option.textContent = status;
        statusFilter.appendChild(option);
    });
    
    // 页面选项
    const pages = [...new Set(ordersData.map(order => order.page))].sort((a, b) => a - b);
    pages.forEach(page => {
        const option = document.createElement('option');
        option.value = page;
        option.textContent = `第 ${page} 页`;
        pageSelect.appendChild(option);
    });
}

// 应用过滤器
function applyFilters() {
    const statusValue = statusFilter.value;
    const searchValue = searchInput.value.toLowerCase().trim();
    const pageValue = pageSelect.value;
    
    filteredOrders = ordersData.filter(order => {
        const matchesStatus = !statusValue || order.orderInfo?.status?.name === statusValue;
        const matchesSearch = !searchValue || 
            order.orderInfo?.orderId?.toLowerCase().includes(searchValue) ||
            order.orderInfo?.buyer?.name?.toLowerCase().includes(searchValue) ||
            order.orderInfo?.seller?.name?.toLowerCase().includes(searchValue);
        const matchesPage = !pageValue || order.page == pageValue;
        
        return matchesStatus && matchesSearch && matchesPage;
    });
    
    currentDisplayPage = 1;
    updateStats();
    displayOrders();
    updatePagination();
}

// 更新统计信息
function updateStats() {
    const totalOrders = filteredOrders.length;
    const totalPages = Math.max(1, Math.ceil(totalOrders / ordersPerPage));
    const totalAmount = filteredOrders.reduce((sum, order) => {
        return sum + (order.orderInfo?.paidPrice || 0);
    }, 0);
    
    totalOrdersEl.textContent = totalOrders;
    totalPagesEl.textContent = totalPages;
    totalAmountEl.textContent = `¥${totalAmount.toLocaleString()}`;
}

// 显示订单
function displayOrders() {
    const startIndex = (currentDisplayPage - 1) * ordersPerPage;
    const endIndex = startIndex + ordersPerPage;
    const ordersToShow = filteredOrders.slice(startIndex, endIndex);
    
    if (ordersToShow.length === 0) {
        ordersList.innerHTML = '<div class="no-orders">没有找到匹配的订单</div>';
        return;
    }
    
    ordersList.innerHTML = ordersToShow.map(order => createOrderCard(order)).join('');
}

// 创建订单卡片
function createOrderCard(order) {
    const orderInfo = order.orderInfo || {};
    const products = order.products || [];
    
    // 格式化时间
    const createdDate = orderInfo.createdAt ? 
        new Date(parseInt(orderInfo.createdAt) * 1000).toLocaleString('zh-CN') : 
        '未知时间';
    
    // 确定状态样式
    const statusClass = getStatusClass(orderInfo.status?.key);
    
    return `
        <div class="order-card">
            <div class="order-header">
                <div class="order-id">订单号: ${orderInfo.orderId || '未知'}</div>
                <div class="order-status ${statusClass}">${orderInfo.status?.name || '未知状态'}</div>
            </div>
            
            <div class="order-content">
                <div class="order-info">
                    <div class="info-row">
                        <span class="info-label">👤 买家:</span>
                        <span class="info-value">${orderInfo.buyer?.name || '未知'}</span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">🏪 卖家:</span>
                        <span class="info-value">${orderInfo.seller?.name || '未知'}</span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">📱 联系:</span>
                        <span class="info-value">${orderInfo.buyer?.phone || '未知'}</span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">⏰ 下单:</span>
                        <span class="info-value">${createdDate}</span>
                    </div>
                </div>
                
                <div class="order-details">
                    <div class="info-row">
                        <span class="info-label">📦 收货人:</span>
                        <span class="info-value">${orderInfo.receiver || '未知'}</span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">📍 地址:</span>
                        <span class="info-value" title="${orderInfo.address || ''}">${
                            orderInfo.address ? 
                            (orderInfo.address.length > 50 ? orderInfo.address.substring(0, 50) + '...' : orderInfo.address) : 
                            '未知'
                        }</span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">💰 订单金额:</span>
                        <span class="info-value price-highlight">¥${(orderInfo.orderPrice || 0).toLocaleString()}</span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">💳 实付金额:</span>
                        <span class="info-value price-highlight">¥${(orderInfo.paidPrice || 0).toLocaleString()}</span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">🚚 运费:</span>
                        <span class="info-value">¥${(orderInfo.expressPrice || 0).toLocaleString()}</span>
                    </div>
                </div>
            </div>
            
            ${products.length > 0 ? createProductsSection(products) : ''}
        </div>
    `;
}

// 创建商品区域
function createProductsSection(products) {
    return `
        <div class="products-section">
            <div class="products-title">🛍️ 商品清单 (${products.length})</div>
            <div class="products-list">
                ${products.map(product => createProductItem(product)).join('')}
            </div>
        </div>
    `;
}

// 创建商品项
function createProductItem(product) {
    const specs = product.specValues || [];
    const imageUrl = product.cover || product.whiteBgPng || '';
    
    return `
        <div class="product-item">
            ${imageUrl ? `<img src="${imageUrl}" alt="${product.productName}" class="product-image" onerror="this.style.display='none'">` : ''}
            <div class="product-info">
                <div class="product-name">${product.productName || '未知商品'}</div>
                <div class="product-specs">
                    ${specs.map(spec => `
                        <span class="spec-tag" style="background-color: ${spec.labelColor}; color: ${spec.color}">
                            ${spec.name}: ${spec.value}
                        </span>
                    `).join('')}
                </div>
                <div class="product-price">¥${(product.price || 0).toLocaleString()} × ${product.amount || 1}</div>
                ${product.description ? `<div style="font-size: 0.8rem; color: #666; margin-top: 5px;">${product.description}</div>` : ''}
            </div>
        </div>
    `;
}

// 获取状态样式类
function getStatusClass(statusKey) {
    const statusMap = {
        'WAIT_SELLER_SEND_GOODS': 'status-wait',
        'WAIT_BUYER_CONFIRM_GOODS': 'status-shipped',
        'TRADE_SUCCESS': 'status-delivered',
        'TRADE_CLOSED': 'status-cancelled',
        'REFUND': 'status-refund'
    };
    
    return statusMap[statusKey] || 'status-wait';
}

// 切换页面
function changePage(direction) {
    const totalPages = Math.ceil(filteredOrders.length / ordersPerPage);
    const newPage = currentDisplayPage + direction;
    
    if (newPage >= 1 && newPage <= totalPages) {
        currentDisplayPage = newPage;
        displayOrders();
        updatePagination();
        
        // 滚动到顶部
        document.querySelector('.orders-container').scrollIntoView({ 
            behavior: 'smooth' 
        });
    }
}

// 更新分页信息
function updatePagination() {
    const totalPages = Math.max(1, Math.ceil(filteredOrders.length / ordersPerPage));
    
    pageInfo.textContent = `第 ${currentDisplayPage} 页，共 ${totalPages} 页`;
    
    prevBtn.disabled = currentDisplayPage <= 1;
    nextBtn.disabled = currentDisplayPage >= totalPages;
}

// 添加样式到页面
const style = document.createElement('style');
style.textContent = `
    .no-orders, .error {
        text-align: center;
        padding: 40px;
        color: #666;
        font-size: 1.1rem;
        background: white;
        border-radius: 15px;
        margin: 20px 0;
    }
    
    .error {
        color: #e74c3c;
        border: 2px solid #fadbd8;
        background: #fdf2f2;
    }
`;
document.head.appendChild(style); 