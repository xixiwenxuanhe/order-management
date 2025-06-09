// 订单管理系统 JavaScript

let ordersData = [];
let currentPage = 1;
let totalPages = 1;

// 初始化
document.addEventListener('DOMContentLoaded', function() {
    setupEventListeners();
});

function setupEventListeners() {
    // 文件上传表单提交
    document.getElementById('uploadForm').addEventListener('submit', handleFileUpload);
    
    // 文件选择变化
    document.getElementById('fileInput').addEventListener('change', function(e) {
        const file = e.target.files[0];
        if (file) {
            validateFile(file);
        }
    });
}

function validateFile(file) {
    const maxSize = 16 * 1024 * 1024; // 16MB
    const allowedTypes = ['application/json', 'text/plain'];
    
    if (file.size > maxSize) {
        showError('文件大小不能超过 16MB');
        return false;
    }
    
    // 允许JSON/TXT文件，或者没有扩展名的文件（如1749469724351_body）
    const fileName = file.name.toLowerCase();
    const hasValidExtension = fileName.endsWith('.json') || fileName.endsWith('.txt');
    const hasValidType = allowedTypes.includes(file.type);
    const hasNoExtension = !fileName.includes('.');
    
    if (!hasValidType && !hasValidExtension && !hasNoExtension) {
        showError('只支持 JSON、TXT 格式文件或无扩展名的数据文件');
        return false;
    }
    
    return true;
}

async function handleFileUpload(event) {
    event.preventDefault();
    
    const fileInput = document.getElementById('fileInput');
    const file = fileInput.files[0];
    
    if (!file) {
        showError('请选择一个文件');
        return;
    }
    
    if (!validateFile(file)) {
        return;
    }
    
    showLoading(true);
    hideError();
    
    try {
        const text = await readFileAsText(file);
        const data = JSON.parse(text);
        
        processOrderData(data);
        
    } catch (error) {
        console.error('处理文件时出错:', error);
        showError('文件格式错误或解析失败: ' + error.message);
    } finally {
        showLoading(false);
    }
}

function readFileAsText(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result);
        reader.onerror = () => reject(reader.error);
        reader.readAsText(file, 'utf-8');
    });
}

function processOrderData(rawData) {
    // 检查数据结构
    if (rawData.code !== 0) {
        showError(`响应码不为0，当前为 ${rawData.code}`);
        return;
    }
    
    // 提取订单列表
    const orderList = rawData.data?.rowList || [];
    
    if (orderList.length === 0) {
        showError('未找到订单数据');
        return;
    }
    
    // 处理每个订单
    ordersData = [];
    for (const order of orderList) {
        try {
            const keyInfo = extractKeyOrderInfo(order);
            ordersData.push(keyInfo);
        } catch (error) {
            console.warn('处理订单时出错:', error);
            continue;
        }
    }
    
    if (ordersData.length === 0) {
        showError('没有有效的订单数据');
        return;
    }
    
    // 显示结果
    displayOrdersData();
}

function extractKeyOrderInfo(orderData) {
    const orderInfo = orderData.orderInfo || {};
    const products = orderData.products || [];
    
    return {
        orderId: orderInfo.orderId || '',
        status: {
            name: orderInfo.status?.name || '',
            key: orderInfo.status?.key || ''
        },
        orderType: {
            name: orderInfo.orderType?.name || '',
            key: orderInfo.orderType?.key || ''
        },
        createdAt: orderInfo.createdAt || '',
        paidAt: orderInfo.paidAt || '',
        deliverPattern: {
            name: orderInfo.deliverPattern?.name || '',
            key: orderInfo.deliverPattern?.key || ''
        },
        buyer: {
            id: orderInfo.buyer?.id || '',
            name: orderInfo.buyer?.name || '',
            phone: orderInfo.buyer?.phone || ''
        },
        seller: {
            id: orderInfo.seller?.id || '',
            name: orderInfo.seller?.name || '',
            phone: orderInfo.seller?.phone || ''
        },
        receiver: {
            name: orderInfo.receiver || '',
            phone: orderInfo.receiverPhone || '',
            address: orderInfo.address || '',
            province: orderInfo.receiverProvince || '',
            city: orderInfo.receiverCity || '',
            district: orderInfo.receiverDistrict || ''
        },
        pricing: {
            orderPrice: orderInfo.orderPrice || 0,
            expressPrice: orderInfo.expressPrice || 0,
            paidPrice: orderInfo.paidPrice || 0,
            originalPrice: orderInfo.orderOriginalPrice || 0,
            afterDiscountPrice: orderInfo.afterDiscountPrice || 0
        },
        products: products.map(product => ({
            productId: product.productId || '',
            productName: product.productName || '',
            unitPrice: product.uintPrice || 0,
            amount: product.amount || 0,
            totalPrice: product.price || 0,
            description: product.description || '',
            specValues: product.specValues || []
        })),
        availableActions: (orderData.activeActions || []).map(action => ({
            action: action.action || '',
            actionName: action.actionName || ''
        })),
        productNum: orderData.productNum || '0',
        relatedId: orderInfo.relatedId || '',
        relatedType: orderInfo.relatedType || '',
        expiredAt: orderInfo.expiredAt || '0'
    };
}

function displayOrdersData() {
    currentPage = 1;
    totalPages = ordersData.length;
    
    // 显示统计信息
    displayStats();
    
    // 显示订单
    displayCurrentOrder();
    
    // 显示容器
    document.getElementById('statsCard').style.display = 'block';
    document.getElementById('ordersContainer').style.display = 'block';
}

function displayStats() {
    document.getElementById('totalOrders').textContent = ordersData.length;
    
    // 统计订单状态
    const statusCount = {};
    ordersData.forEach(order => {
        const status = order.status.name;
        statusCount[status] = (statusCount[status] || 0) + 1;
    });
    
    // 显示状态统计
    const statusStatsContainer = document.getElementById('statusStats');
    statusStatsContainer.innerHTML = '';
    
    Object.entries(statusCount).forEach(([status, count]) => {
        const badge = document.createElement('span');
        badge.className = 'stat-badge';
        badge.textContent = `${status}: ${count}个`;
        statusStatsContainer.appendChild(badge);
    });
}

function displayCurrentOrder() {
    if (ordersData.length === 0) return;
    
    const order = ordersData[currentPage - 1];
    const container = document.getElementById('orderContent');
    
    container.innerHTML = generateOrderHTML(order);
    
    // 更新分页信息
    document.getElementById('currentPage').textContent = currentPage;
    document.getElementById('totalPages').textContent = totalPages;
    
    // 更新分页按钮状态
    updatePaginationButtons();
}

function generateOrderHTML(order) {
    return `
        <div class="order-card card fade-in">
            <div class="order-header">
                <div class="d-flex justify-content-between align-items-center">
                    <div>
                        <h6 class="mb-1">订单号: ${order.orderId}</h6>
                        <small>创建时间: ${formatTimestamp(order.createdAt)}</small>
                    </div>
                    <span class="status-badge ${getStatusClass(order.status.key)}">
                        ${order.status.name}
                    </span>
                </div>
            </div>
            <div class="order-body">
                <div class="row">
                    <div class="col-md-6">
                        <h6><i class="bi bi-person"></i> 买家信息</h6>
                        <div class="contact-info">
                            <div><strong>姓名:</strong> ${order.buyer.name}</div>
                            <div><strong>电话:</strong> ${order.buyer.phone}</div>
                        </div>
                        
                        <h6 class="mt-3"><i class="bi bi-shop"></i> 卖家信息</h6>
                        <div class="contact-info">
                            <div><strong>姓名:</strong> ${order.seller.name}</div>
                            <div><strong>电话:</strong> ${order.seller.phone}</div>
                        </div>
                    </div>
                    <div class="col-md-6">
                        <h6><i class="bi bi-geo-alt"></i> 收货信息</h6>
                        <div class="address-info">
                            <div><strong>收货人:</strong> ${order.receiver.name}</div>
                            <div><strong>电话:</strong> ${order.receiver.phone}</div>
                            <div><strong>地址:</strong> ${order.receiver.province} ${order.receiver.city} ${order.receiver.district}</div>
                            <div><strong>详细地址:</strong> ${order.receiver.address}</div>
                        </div>
                    </div>
                </div>
                
                <h6 class="mt-3"><i class="bi bi-box"></i> 商品信息</h6>
                ${order.products.map(product => `
                    <div class="product-item">
                        <div class="d-flex justify-content-between align-items-start">
                            <div class="flex-grow-1">
                                <h6 class="mb-2">${product.productName}</h6>
                                <div class="mb-2">
                                    ${product.specValues.map(spec => 
                                        `<span class="product-spec">${spec.name}: ${spec.value}</span>`
                                    ).join('')}
                                </div>
                                <div class="text-muted small">${product.description}</div>
                            </div>
                            <div class="text-end">
                                <div><strong>¥${product.unitPrice}</strong> × ${product.amount}</div>
                                <div class="text-primary"><strong>¥${product.totalPrice}</strong></div>
                            </div>
                        </div>
                    </div>
                `).join('')}
                
                <div class="price-section">
                    <h6><i class="bi bi-calculator"></i> 价格明细</h6>
                    <div class="price-item">
                        <span>商品价格:</span>
                        <span>¥${order.pricing.orderPrice}</span>
                    </div>
                    <div class="price-item">
                        <span>运费:</span>
                        <span>¥${order.pricing.expressPrice}</span>
                    </div>
                    <div class="price-item">
                        <span>原价:</span>
                        <span>¥${order.pricing.originalPrice}</span>
                    </div>
                    <div class="price-item price-total">
                        <span>实付金额:</span>
                        <span>¥${order.pricing.paidPrice}</span>
                    </div>
                </div>
                
                <div class="actions-section">
                    <h6><i class="bi bi-gear"></i> 可用操作</h6>
                    ${order.availableActions.map(action => 
                        `<button class="btn btn-outline-primary btn-sm action-btn" disabled>
                            ${action.actionName}
                        </button>`
                    ).join('')}
                </div>
            </div>
        </div>
    `;
}

function getStatusClass(statusKey) {
    const statusMap = {
        'WAIT_BUYER_PAY': 'status-wait-pay',
        'WAIT_SELLER_SEND_GOODS': 'status-wait-send',
        'WAIT_BUYER_CONFIRM_GOODS': 'status-wait-receive',
        'BUYER_CONFIRM_GOODS': 'status-success'
    };
    return statusMap[statusKey] || 'status-wait-pay';
}

function formatTimestamp(timestamp) {
    if (!timestamp || timestamp === '0') {
        return '未设置';
    }
    
    try {
        const date = new Date(parseInt(timestamp) * 1000);
        return date.toLocaleString('zh-CN');
    } catch {
        return timestamp;
    }
}

function updatePaginationButtons() {
    const prevBtn = document.querySelector('button[onclick="previousPage()"]');
    const nextBtn = document.querySelector('button[onclick="nextPage()"]');
    
    prevBtn.disabled = currentPage <= 1;
    nextBtn.disabled = currentPage >= totalPages;
}

function previousPage() {
    if (currentPage > 1) {
        currentPage--;
        displayCurrentOrder();
    }
}

function nextPage() {
    if (currentPage < totalPages) {
        currentPage++;
        displayCurrentOrder();
    }
}

function clearData() {
    if (confirm('确定要清除所有数据吗？')) {
        ordersData = [];
        currentPage = 1;
        totalPages = 1;
        
        document.getElementById('statsCard').style.display = 'none';
        document.getElementById('ordersContainer').style.display = 'none';
        document.getElementById('fileInput').value = '';
        
        hideError();
    }
}

function showLoading(show) {
    document.getElementById('loadingAlert').style.display = show ? 'block' : 'none';
}

function showError(message) {
    const errorAlert = document.getElementById('errorAlert');
    errorAlert.innerHTML = `<i class="bi bi-exclamation-triangle"></i> ${message}`;
    errorAlert.style.display = 'block';
}

function hideError() {
    document.getElementById('errorAlert').style.display = 'none';
} 