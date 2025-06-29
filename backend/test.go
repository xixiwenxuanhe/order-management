package main

import (
	"bufio"
	"bytes"
	"compress/gzip"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"strconv"
	"strings"
	"sync"
	"time"
)

// 订单详情结构体 - 只定义需要的字段
type OrderDetail struct {
	Success bool   `json:"success"`
	Message string `json:"message"`
	Data    struct {
		OrderDetail struct {
			OrderInfo struct {
				OrderID string `json:"orderId"`
				Status  struct {
					Name string `json:"name"`
				} `json:"status"`
				PaidAt string `json:"paidAt"`
			} `json:"orderInfo"`
			Products []struct {
				ProductName string  `json:"productName"`
				Price       float64 `json:"price"`
				Amount      int     `json:"amount"`
			} `json:"products"`
		} `json:"order_detail"`
	} `json:"data"`
}

// 请求参数结构体
type RequestParams struct {
	XRequestSign      string `json:"x_request_sign"`
	XRequestTimestamp string `json:"x_request_timestamp"`
	Authorization     string `json:"authorization"`
	OrderID           string `json:"order_id"`
}

// 数据库状态API响应结构体
type DatabaseStatsResponse struct {
	Success bool   `json:"success"`
	Message string `json:"message"`
	Data    struct {
		TotalOrders           int      `json:"total_orders"`
		TotalRecords          int      `json:"total_records"`
		LatestTime            string   `json:"latest_time"`
		LatestOrderID         string   `json:"latest_order_id"`
		IncompleteEarliestTime string  `json:"incomplete_earliest_time"`
		IncompleteEarliestOrderID string `json:"incomplete_earliest_order_id"`
		IncompleteOrderIDs    []string `json:"incomplete_order_ids"`
		IncompleteOrdersCount int      `json:"incomplete_orders_count"`
		OrdersNeedDetails     int      `json:"orders_need_details"`
	} `json:"data"`
}

// API配置
const (
	API_URL         = "https://api.qiandao.cn/order-web/user/v3/load-order-details"
	DB_STATS_URL    = "http://localhost:8000/api/db-stats"
	MAX_WORKERS     = 200
)

func main() {
	fmt.Println("=== 订单详情获取器（测试版本） ===")
	
	// 获取用户输入
	params := getUserInput()
	
	// 从API获取非交易成功的订单ID列表
	orderIDs, err := getIncompleteOrderIDs()
	if err != nil {
		log.Fatal("获取订单ID列表失败:", err)
	}
	
	if len(orderIDs) == 0 {
		fmt.Println("没有需要获取详情的订单")
		return
	}
	
	fmt.Printf("找到 %d 个非交易成功的订单需要测试\n", len(orderIDs))
	
	// 并发处理订单（仅测试，不保存到数据库）
	processOrdersConcurrently(orderIDs, params)
	
	fmt.Println("所有订单测试完成！")
}

// 获取用户输入
func getUserInput() RequestParams {
	reader := bufio.NewReader(os.Stdin)
	
	fmt.Print("请输入 authorization: ")
	authorization, _ := reader.ReadString('\n')
	authorization = strings.TrimSpace(authorization)
	
	fmt.Print("请输入 x_request_sign: ")
	xRequestSign, _ := reader.ReadString('\n')
	xRequestSign = strings.TrimSpace(xRequestSign)
	
	fmt.Print("请输入 x_request_timestamp: ")
	xRequestTimestamp, _ := reader.ReadString('\n')
	xRequestTimestamp = strings.TrimSpace(xRequestTimestamp)
	
	return RequestParams{
		XRequestSign:      xRequestSign,
		XRequestTimestamp: xRequestTimestamp,
		Authorization:     authorization,
	}
}

// 从数据库状态API获取非交易成功的订单ID列表
func getIncompleteOrderIDs() ([]string, error) {
	fmt.Println("正在从API获取非交易成功的订单ID列表...")
	
	resp, err := http.Get(DB_STATS_URL)
	if err != nil {
		return nil, fmt.Errorf("请求数据库状态API失败: %v", err)
	}
	defer resp.Body.Close()
	
	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("读取响应失败: %v", err)
	}
	
	var statsResponse DatabaseStatsResponse
	err = json.Unmarshal(body, &statsResponse)
	if err != nil {
		return nil, fmt.Errorf("解析响应失败: %v", err)
	}
	
	if !statsResponse.Success {
		return nil, fmt.Errorf("API返回错误: %s", statsResponse.Message)
	}
	
	fmt.Printf("数据库状态信息:\n")
	fmt.Printf("- 总订单数: %d\n", statsResponse.Data.TotalOrders)
	fmt.Printf("- 总记录数: %d\n", statsResponse.Data.TotalRecords)
	fmt.Printf("- 非交易成功订单数: %d\n", statsResponse.Data.IncompleteOrdersCount)
	fmt.Printf("- 最早未完成订单ID: %s\n", statsResponse.Data.IncompleteEarliestOrderID)
	
	return statsResponse.Data.IncompleteOrderIDs, nil
}

// 并发处理订单（仅测试，不保存数据库）
func processOrdersConcurrently(orderIDs []string, params RequestParams) {
	// 创建工作通道
	orderChan := make(chan string, len(orderIDs))
	
	// 填充订单ID到通道
	for _, orderID := range orderIDs {
		orderChan <- orderID
	}
	close(orderChan)
	
	// 创建等待组
	var wg sync.WaitGroup
	
	// 统计变量
	var successCount, failCount int64
	var mu sync.Mutex
	
	// 启动工作协程
	workerCount := MAX_WORKERS
	if len(orderIDs) < MAX_WORKERS {
		workerCount = len(orderIDs)
	}
	
	fmt.Printf("启动 %d 个工作协程进行测试...\n", workerCount)
	
	for i := 0; i < workerCount; i++ {
		wg.Add(1)
		go func(workerID int) {
			defer wg.Done()
			
			for orderID := range orderChan {
				success := processOrder(orderID, params)
				
				mu.Lock()
				if success {
					successCount++
				} else {
					failCount++
				}
				
				if (successCount+failCount)%10 == 0 {
					fmt.Printf("测试进度: 成功 %d, 失败 %d, 总计 %d/%d\n", 
						successCount, failCount, successCount+failCount, len(orderIDs))
				}
				mu.Unlock()
			}
		}(i)
	}
	
	// 等待所有协程完成
	wg.Wait()
	
	fmt.Printf("测试完成! 成功: %d, 失败: %d, 总计: %d\n", successCount, failCount, successCount+failCount)
}

// 处理单个订单（仅测试，不保存数据库）
func processOrder(orderID string, params RequestParams) bool {
	// 构建请求参数
	requestParams := RequestParams{
		XRequestSign:      params.XRequestSign,
		XRequestTimestamp: params.XRequestTimestamp,
		Authorization:     params.Authorization,
		OrderID:           orderID,
	}
	
	// 发送HTTP请求
	orderDetail, err := fetchOrderDetail(requestParams)
	if err != nil {
		fmt.Printf("订单 %s 请求失败: %v\n", orderID, err)
		return false
	}
	
	// 只打印订单信息，不保存到数据库
	fmt.Printf("订单 %s 测试成功: 状态=%s, 商品数=%d\n", 
		orderDetail.Data.OrderDetail.OrderInfo.OrderID,
		orderDetail.Data.OrderDetail.OrderInfo.Status.Name,
		len(orderDetail.Data.OrderDetail.Products))
	
	return true
}

// 发送HTTP请求获取订单详情
func fetchOrderDetail(params RequestParams) (*OrderDetail, error) {
	// 构建请求体 - 直接调用外部API
	requestBody := map[string]string{
		"orderId": params.OrderID,
	}
	
	jsonBody, err := json.Marshal(requestBody)
	if err != nil {
		return nil, fmt.Errorf("构建请求体失败: %v", err)
	}
	
	// 创建HTTP请求
	req, err := http.NewRequest("POST", API_URL, bytes.NewBuffer(jsonBody))
	if err != nil {
		return nil, fmt.Errorf("创建请求失败: %v", err)
	}
	
	// 设置完整的请求头（与Python后端完全一致）
	req.Header.Set("Accept-Encoding", "gzip")
	req.Header.Set("X-Request-Version", "5.91.1")
	req.Header.Set("X-Request-Sign-Type", "RSA2")
	req.Header.Set("X-Echo-Teen-Mode", "false")
	req.Header.Set("X-Request-Utm_source", "xiaomi")
	req.Header.Set("X-Request-Package-Sign-Version", "0.0.3")
	req.Header.Set("X-Request-Id", "")
	req.Header.Set("X-Client-Package-Id", "1006")
	req.Header.Set("X-Request-Package-Id", "1006")
	req.Header.Set("X-Device-Id", "6ec1e3cac888f55d")
	req.Header.Set("User-Agent", "Kuril+/5.91.1 (Android 15)")
	req.Header.Set("X-Echo-Install-Id", "ODY5NjE4MjM0NDA2NTAyOTQ5")
	req.Header.Set("Cache-Control", "max-age=3600")
	req.Header.Set("X-Echo-City-Code", "")
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Downloadchannel", "xiaomi")
	req.Header.Set("X-Request-Sign-Version", "v1")
	req.Header.Set("Referer", "https://qiandao.cn")
	req.Header.Set("X-Request-Channel", "xiaomi")
	req.Header.Set("X-Echo-Region", "CN")
	req.Header.Set("Accept-Language", "zh-CN")
	req.Header.Set("Host", "api.qiandao.cn")
	req.Header.Set("X-Request-Device", "android")
	
	// 设置动态认证信息
	req.Header.Set("X-Request-Timestamp", params.XRequestTimestamp)
	req.Header.Set("X-Request-Sign", params.XRequestSign)
	req.Header.Set("Authorization", params.Authorization)
	
	// 发送请求
	client := &http.Client{Timeout: 60 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("发送请求失败: %v", err)
	}
	defer resp.Body.Close()
	
	// 读取响应并处理gzip解压缩
	var reader io.Reader = resp.Body
	if resp.Header.Get("Content-Encoding") == "gzip" {
		gzipReader, err := gzip.NewReader(resp.Body)
		if err != nil {
			return nil, fmt.Errorf("创建gzip读取器失败: %v", err)
		}
		defer gzipReader.Close()
		reader = gzipReader
	}
	
	body, err := io.ReadAll(reader)
	if err != nil {
		return nil, fmt.Errorf("读取响应失败: %v", err)
	}
	
	// 解析原始API响应
	var apiResponse struct {
		Code    int    `json:"code"`
		Message string `json:"message"`
		Data    struct {
			Details  map[string]interface{} `json:"details"`
			Products []struct {
				ProductName string  `json:"productName"`
				Price       float64 `json:"price"`
				Amount      int     `json:"amount"`
			} `json:"products"`
		} `json:"data"`
	}
	
	err = json.Unmarshal(body, &apiResponse)
	if err != nil {
		return nil, fmt.Errorf("解析响应失败: %v", err)
	}
	
	// 检查API响应状态
	if apiResponse.Code != 0 {
		return nil, fmt.Errorf("API返回错误: %s", apiResponse.Message)
	}
	
	// 转换为我们的结构体格式
	orderDetail := &OrderDetail{
		Success: true,
		Message: "获取订单详情成功",
		Data: struct {
			OrderDetail struct {
				OrderInfo struct {
					OrderID string `json:"orderId"`
					Status  struct {
						Name string `json:"name"`
					} `json:"status"`
					PaidAt string `json:"paidAt"`
				} `json:"orderInfo"`
				Products []struct {
					ProductName string  `json:"productName"`
					Price       float64 `json:"price"`
					Amount      int     `json:"amount"`
				} `json:"products"`
			} `json:"order_detail"`
		}{},
	}
	
	// 提取订单基本信息
	if orderId, ok := apiResponse.Data.Details["orderId"].(string); ok {
		orderDetail.Data.OrderDetail.OrderInfo.OrderID = orderId
	}
	if paidAt, ok := apiResponse.Data.Details["paidAt"].(string); ok {
		orderDetail.Data.OrderDetail.OrderInfo.PaidAt = paidAt
	}
	if status, ok := apiResponse.Data.Details["status"].(map[string]interface{}); ok {
		if name, ok := status["name"].(string); ok {
			orderDetail.Data.OrderDetail.OrderInfo.Status.Name = name
		}
	}
	
	// 复制商品信息
	orderDetail.Data.OrderDetail.Products = apiResponse.Data.Products
	
	return orderDetail, nil
}

// 将时间戳转换为日期格式
func timestampToDate(timestampStr string) string {
	if timestampStr == "" {
		return ""
	}
	
	timestamp, err := strconv.ParseInt(timestampStr, 10, 64)
	if err != nil {
		return timestampStr
	}
	
	return time.Unix(timestamp, 0).Format("2006-01-02 15:04:05")
} 


