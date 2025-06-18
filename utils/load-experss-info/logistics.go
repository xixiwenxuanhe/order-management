package main

import (
	"bufio"
	"bytes"
	"compress/gzip"
	"encoding/json"
	"io"
	"log"
	"net/http"
	"os"
	"strings"
	"sync"
)

// 状态信息结构
type StatusInfo struct {
	Orders []OrderStatus `json:"orders"`
}

type OrderStatus struct {
	OrderId    string `json:"orderId"`
	StatusName string `json:"statusName"`
}

// HTTP请求结构
type HTTPRequest struct {
	Method  string
	URL     string
	Headers map[string]string
	Body    string
}

// 响应结构
type ExpressResponse struct {
	Code string `json:"code"`
	Data []struct {
		CompanyCode string `json:"companyCode"`
		ExpressNo   string `json:"expressNo"`
		CompanyName string `json:"companyName"`
	} `json:"data"`
}

// 结果结构
type LogisticsResult struct {
	OrderId     string `json:"orderId"`
	ExpressNo   string `json:"expressNo"`
	CompanyName string `json:"companyName"`
}

// 读取状态信息文件
func readStatusInfo() (*StatusInfo, error) {
	data, err := os.ReadFile("status_info.json")
	if err != nil {
		return nil, err
	}
	var statusInfo StatusInfo
	json.Unmarshal(data, &statusInfo)
	return &statusInfo, nil
}

// 解析HTTP文件
func parseHTTPFile() (*HTTPRequest, error) {
	file, err := os.Open("http_req_express.hcy")
	if err != nil {
		return nil, err
	}
	defer file.Close()

	scanner := bufio.NewScanner(file)
	lines := []string{}
	for scanner.Scan() {
		lines = append(lines, scanner.Text())
	}

	requestLine := strings.Fields(lines[0])
	method := requestLine[0]
	path := requestLine[1]

	headers := make(map[string]string)
	bodyStart := -1
	host := ""

	for i := 1; i < len(lines); i++ {
		line := lines[i]
		if strings.TrimSpace(line) == "" {
			bodyStart = i + 1
			break
		}
		if strings.Contains(line, ":") {
			parts := strings.SplitN(line, ":", 2)
			key := strings.TrimSpace(parts[0])
			value := strings.TrimSpace(parts[1])
			headers[key] = value
			if strings.ToLower(key) == "host" {
				host = value
			}
		}
	}

	url := "https://" + host + path
	body := ""
	if bodyStart != -1 && bodyStart < len(lines) {
		for i := bodyStart; i < len(lines); i++ {
			body += strings.TrimSpace(lines[i])
		}
	}

	return &HTTPRequest{method, url, headers, body}, nil
}

// 读取签名文件
func readSignatureFiles() (string, string) {
	timestampData, _ := os.ReadFile("x-request-timestamp.txt")
	signData, _ := os.ReadFile("x-request-sign.txt")
	return strings.TrimSpace(string(timestampData)), strings.TrimSpace(string(signData))
}

// 发送快递查询请求
func queryExpress(orderId string, httpReq *HTTPRequest, timestamp, sign string) *LogisticsResult {
	var bodyMap map[string]interface{}
	json.Unmarshal([]byte(httpReq.Body), &bodyMap)
	bodyMap["orderId"] = orderId
	newBody, _ := json.Marshal(bodyMap)

	req, _ := http.NewRequest(httpReq.Method, httpReq.URL, bytes.NewReader(newBody))

	for key, value := range httpReq.Headers {
		if strings.ToLower(key) != "content-length" {
			req.Header.Set(key, value)
		}
	}
	req.Header.Set("x-request-timestamp", timestamp)
	req.Header.Set("x-request-sign", sign)

	client := &http.Client{}
	resp, _ := client.Do(req)
	defer resp.Body.Close()

	// 处理gzip压缩的响应
	var reader io.Reader = resp.Body
	if resp.Header.Get("Content-Encoding") == "gzip" {
		gzipReader, err := gzip.NewReader(resp.Body)
		if err == nil {
			defer gzipReader.Close()
			reader = gzipReader
		}
	}

	body, _ := io.ReadAll(reader)

	// 输出每个订单的响应
	log.Printf("订单 %s 响应: %s", orderId, string(body))

	var expressResp ExpressResponse
	json.Unmarshal(body, &expressResp)

	if len(expressResp.Data) > 0 {
		express := expressResp.Data[0]
		return &LogisticsResult{
			OrderId:     orderId,
			ExpressNo:   express.ExpressNo,
			CompanyName: express.CompanyName,
		}
	}

	return &LogisticsResult{
		OrderId: orderId,
	}
}

func main() {
	statusInfo, err := readStatusInfo()
	if err != nil {
		log.Fatal(err)
	}

	var targetOrders []string
	for _, order := range statusInfo.Orders {
		if order.StatusName == "待买家收货" {
			targetOrders = append(targetOrders, order.OrderId)
		}
	}

	if len(targetOrders) == 0 {
		return
	}

	log.Printf("一共有 %d 个订单要处理", len(targetOrders))

	httpReq, _ := parseHTTPFile()
	timestamp, sign := readSignatureFiles()

	var wg sync.WaitGroup
	results := make(chan *LogisticsResult, len(targetOrders))
	semaphore := make(chan struct{}, 5000)

	for _, orderId := range targetOrders {
		wg.Add(1)
		go func(id string) {
			defer wg.Done()
			semaphore <- struct{}{}
			defer func() { <-semaphore }()

			result := queryExpress(id, httpReq, timestamp, sign)
			results <- result
		}(orderId)
	}

	go func() {
		wg.Wait()
		close(results)
	}()

	var allResults []*LogisticsResult
	successCount := 0
	for result := range results {
		allResults = append(allResults, result)
		if result.ExpressNo != "" {
			successCount++
		}
	}

	successRate := float64(successCount) / float64(len(allResults)) * 100
	log.Printf("处理完成，成功率: %.1f%% (%d/%d)", successRate, successCount, len(allResults))

	outputData := map[string]interface{}{
		"results": allResults,
	}

	outputBytes, _ := json.MarshalIndent(outputData, "", "  ")
	os.WriteFile("logistics_results.json", outputBytes, 0644)
}
