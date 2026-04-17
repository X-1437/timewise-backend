from datetime import datetime
import uuid
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import FileResponse
from bson import ObjectId
from app.database import get_db
from app.core.security import decode_token

router = APIRouter(prefix="/projects/{project_id}/report", tags=["报告"])


async def get_current_user_id(request: Request) -> str:
    auth_header = request.headers.get("Authorization", "")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未授权")
    
    token = auth_header.replace("Bearer ", "")
    payload = decode_token(token)
    
    if not payload:
        raise HTTPException(status_code=401, detail="无效的Token")
    
    return payload.get("user_id", "")


@router.get("/options")
async def get_report_options(project_id: str, user_id: str = Depends(get_current_user_id)):
    return {
        "modules": [
            {"key": "overview", "name": "数据概览", "description": "项目基本信息和数据统计"},
            {"key": "eda", "name": "EDA分析", "description": "数据质量评估和可视化"},
            {"key": "preprocessing", "name": "预处理配置", "description": "数据清洗和预处理参数"},
            {"key": "features", "name": "特征提取", "description": "时域和频域特征"},
            {"key": "forecast", "name": "预测结果", "description": "朴素预测结果和评估指标"}
        ]
    }


@router.post("")
async def generate_report(
    project_id: str,
    request: dict,
    user_id: str = Depends(get_current_user_id)
):
    db = get_db()
    
    try:
        project = await db.projects.find_one({"_id": ObjectId(project_id), "user_id": user_id})
    except:
        raise HTTPException(status_code=400, detail="无效的项目ID")
    
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    modules = request.get("modules", ["overview", "eda", "preprocessing", "features", "forecast"])
    
    report_id = str(uuid.uuid4())
    
    report = {
        "id": report_id,
        "modules": modules,
        "generated_at": datetime.utcnow().isoformat()
    }
    
    existing_reports = project.get("reports", [])
    existing_reports.append(report)
    
    await db.projects.update_one(
        {"_id": ObjectId(project_id)},
        {"$set": {
            "reports": existing_reports,
            "updated_at": datetime.utcnow()
        }}
    )
    
    return {
        "report_id": report_id,
        "download_url": f"/api/v1/projects/{project_id}/report/{report_id}/download"
    }


@router.get("/{report_id}")
async def get_report_preview(project_id: str, report_id: str, user_id: str = Depends(get_current_user_id)):
    db = get_db()
    
    try:
        project = await db.projects.find_one({"_id": ObjectId(project_id), "user_id": user_id})
    except:
        raise HTTPException(status_code=400, detail="无效的项目ID")
    
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    reports = project.get("reports", [])
    report = None
    for r in reports:
        if r.get("id") == report_id:
            report = r
            break
    
    if not report:
        raise HTTPException(status_code=404, detail="报告不存在")
    
    return {
        "id": report_id,
        "modules": report.get("modules", []),
        "generated_at": report.get("generated_at", "")
    }


@router.get("/{report_id}/download")
async def download_report(project_id: str, report_id: str, user_id: str = Depends(get_current_user_id)):
    db = get_db()

    try:
        project = await db.projects.find_one({"_id": ObjectId(project_id), "user_id": user_id})
    except:
        raise HTTPException(status_code=400, detail="无效的项目ID")

    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    reports = project.get("reports", [])
    report = None
    for r in reports:
        if r.get("id") == report_id:
            report = r
            break

    if not report:
        raise HTTPException(status_code=404, detail="报告不存在")

    modules = report.get("modules", [])

    # 生成PDF报告
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib import colors
    from fastapi.responses import StreamingResponse
    import io

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=2*cm, leftMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm)

    styles = getSampleStyleSheet()
    # 创建样式
    normal_style = ParagraphStyle(
        'NormalStyle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
    )
    title_style = ParagraphStyle(
        'TitleStyle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=22,
        spaceAfter=20,
    )
    heading_style = ParagraphStyle(
        'HeadingStyle',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=14,
        leading=18,
        spaceAfter=10,
        spaceBefore=15,
    )

    story = []

    # 标题
    story.append(Paragraph("TimeWise Analysis Report", title_style))
    story.append(Spacer(1, 0.5*cm))

    # 项目基本信息
    project_name = project.get('name', 'Untitled')
    generated_at = report.get('generated_at', '')
    story.append(Paragraph(f"Project: {project_name}", normal_style))
    story.append(Paragraph(f"Generated: {generated_at}", normal_style))
    story.append(Spacer(1, 1*cm))

    # 数据概览
    if "overview" in modules:
        story.append(Paragraph("1. Data Overview", heading_style))
        columns = project.get('columns', [])
        data_config = project.get('data_config', {})
        overview_data = [
            ["Metric", "Value"],
            ["Columns Count", str(len(columns))],
            ["Target Variable", data_config.get('target_column', '-')],
            ["Time Column", data_config.get('time_column', '-')],
        ]
        overview_table = Table(overview_data, colWidths=[6*cm, 8*cm])
        overview_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))
        story.append(overview_table)
        story.append(Spacer(1, 0.5*cm))

    # EDA分析结果
    if "eda" in modules:
        eda = project.get("eda_result", {})
        if eda:
            story.append(Paragraph("2. EDA Analysis Results", heading_style))
            eda_data = [
                ["Metric", "Value"],
                ["Total Rows", str(eda.get('total_rows', 0))],
                ["Total Columns", str(eda.get('total_columns', 0))],
                ["Duplicate Records", str(eda.get('duplicates', 0))],
                ["Outliers Count", str(eda.get('outliers', {}).get('count', 0))],
            ]
            eda_table = Table(eda_data, colWidths=[6*cm, 8*cm])
            eda_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ]))
            story.append(eda_table)
            story.append(Spacer(1, 0.5*cm))

    # 预处理配置
    if "preprocessing" in modules:
        preprocessing = project.get("preprocessing_result", {})
        if preprocessing:
            story.append(Paragraph("3. Preprocessing Configuration", heading_style))
            metrics = preprocessing.get('metrics', {})
            pre_data = [
                ["Metric", "Value"],
                ["Original Rows", str(metrics.get('original_rows', 0))],
                ["Processed Rows", str(metrics.get('processed_rows', 0))],
                ["Missing Values Filled", str(metrics.get('missing_filled', 0))],
                ["Outliers Handled", str(metrics.get('outliers_handled', 0))],
            ]
            pre_table = Table(pre_data, colWidths=[6*cm, 8*cm])
            pre_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ]))
            story.append(pre_table)
            story.append(Spacer(1, 0.5*cm))

    # 特征提取
    if "features" in modules:
        features = project.get("features", [])
        if features:
            story.append(Paragraph("4. Feature Engineering", heading_style))
            latest_feature = features[-1] if features else {}
            feature_config = latest_feature.get('config', {})
            time_features = feature_config.get('time_features', {})
            freq_features = feature_config.get('freq_features', {})

            enabled_time = [k for k, v in time_features.items() if v.get('enabled')]
            enabled_freq = [k for k, v in freq_features.items() if v.get('enabled')]

            feat_data = [
                ["Feature Type", "Enabled Features"],
                ["Time Domain", ", ".join(enabled_time) if enabled_time else "None"],
                ["Frequency Domain", ", ".join(enabled_freq) if enabled_freq else "None"],
            ]
            feat_table = Table(feat_data, colWidths=[5*cm, 9*cm])
            feat_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ]))
            story.append(feat_table)
            story.append(Spacer(1, 0.5*cm))

    # 预测结果
    if "forecast" in modules:
        forecasts = project.get("forecasts", [])
        if forecasts:
            story.append(Paragraph("5. Forecast Results", heading_style))
            latest = forecasts[-1]
            metrics = latest.get("metrics", {})
            method_map = {
                "next_row": "Next Row Shift",
                "same_time": "Same Time Shift",
                "daily_sum": "Daily Sum Shift"
            }
            forecast_data = [
                ["Metric", "Value"],
                ["Method", method_map.get(latest.get('method', '-'), latest.get('method', '-'))],
                ["MAE", f"{metrics.get('mae', 0):.4f}"],
                ["MSE", f"{metrics.get('mse', 0):.4f}"],
                ["RMSE", f"{metrics.get('rmse', 0):.4f}"],
                ["MAPE", f"{metrics.get('mape', 0):.2f}%"],
            ]
            forecast_table = Table(forecast_data, colWidths=[6*cm, 8*cm])
            forecast_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ]))
            story.append(forecast_table)
            story.append(Spacer(1, 1*cm))

    # 页脚
    story.append(Paragraph("Generated by TimeWise Analytics", normal_style))

    doc.build(story)
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=report_{report_id}.pdf"}
    )
