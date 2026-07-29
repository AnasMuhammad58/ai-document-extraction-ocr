from __future__ import annotations
from pathlib import Path
import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

NAVY="#17324d"; GREEN="#3f7d63"; TAN="#d9c9ad"; RED="#b75d4b"; BG="#faf8f3"

def _style(ax,title,ylabel=""):
    ax.set_title(title,loc="left",fontweight="bold",color=NAVY,pad=12)
    ax.set_ylabel(ylabel); ax.grid(axis="y",alpha=.2); ax.set_facecolor(BG)
    ax.spines[["top","right"]].set_visible(False)

def _save(fig,path):
    fig.patch.set_facecolor(BG); fig.tight_layout(); fig.savefig(path,dpi=180,bbox_inches="tight"); plt.close(fig)

def create_evaluation_charts(evaluation_dir:Path,charts:Path):
    fields=pd.read_csv(evaluation_dir/"field_metrics.csv"); fields=fields[fields.expected_count>0]
    fig,ax=plt.subplots(figsize=(11,6)); labels=fields.document_type.str[:3]+" · "+fields.field
    ax.barh(labels,fields.accuracy,color=GREEN); ax.set_xlim(0,1); _style(ax,"Normalized field accuracy","Accuracy")
    _save(fig,charts/"field_accuracy.png")

    quality=pd.read_csv(evaluation_dir/"performance_by_quality.csv")
    fig,ax=plt.subplots(figsize=(10,5)); ax.bar(quality.quality_condition,quality.critical_field_accuracy,color=GREEN)
    ax.tick_params(axis="x",rotation=25); ax.set_ylim(0,1); _style(ax,"Critical-field performance by quality","Accuracy")
    _save(fig,charts/"performance_by_quality.png")

    dtype=pd.read_csv(evaluation_dir/"performance_by_document_type.csv")
    fig,ax=plt.subplots(figsize=(7,5)); x=range(len(dtype))
    ax.bar([i-.18 for i in x],dtype.critical_field_accuracy,.36,label="Critical fields",color=GREEN)
    ax.bar([i+.18 for i in x],dtype.line_item_f1,.36,label="Line items",color=TAN)
    ax.set_xticks(list(x),dtype.document_type); ax.set_ylim(0,1); ax.legend(); _style(ax,"Invoice vs receipt performance","Score")
    _save(fig,charts/"invoice_vs_receipt.png")

    line=pd.read_csv(evaluation_dir/"line_item_metrics.csv"); line=line[line.group_type=="document_type"]
    fig,ax=plt.subplots(figsize=(7,5)); ax.bar(line.group,line.row_f1,color=[GREEN,TAN]); ax.set_ylim(0,1)
    _style(ax,"Line-item row F1","F1"); _save(fig,charts/"line_item_performance.png")

    ocr=pd.read_csv(evaluation_dir/"ocr_text_metrics.csv"); ocr=ocr[ocr.extraction_method=="ocr"]
    grouped=ocr.groupby("quality_condition",as_index=False).cer.mean()
    fig,ax=plt.subplots(figsize=(10,5)); ax.bar(grouped.quality_condition,grouped.cer,color=TAN)
    ax.tick_params(axis="x",rotation=25); _style(ax,"OCR character error rate by quality","CER")
    _save(fig,charts/"ocr_error_by_quality.png")

    confidence=pd.read_csv(evaluation_dir/"confidence_analysis.csv")
    confidence=confidence[confidence.confidence_band.str.contains("-") & (confidence.prediction_count>0)]
    fig,ax=plt.subplots(figsize=(7,5)); ax.scatter(confidence.confidence_band,confidence.critical_field_accuracy,
        s=confidence.prediction_count*8,color=GREEN); ax.set_ylim(0,1)
    _style(ax,"Confidence bins vs critical-field correctness","Critical-field accuracy")
    _save(fig,charts/"confidence_vs_correctness.png")

    errors=pd.read_csv(evaluation_dir/"error_analysis.csv"); counts=errors.error_category.value_counts().head(8)
    fig,ax=plt.subplots(figsize=(9,5)); ax.barh(counts.index[::-1],counts.values[::-1],color=RED)
    _style(ax,"Most frequent extraction error categories","Count"); _save(fig,charts/"error_categories.png")

    docs=pd.read_csv(evaluation_dir/"document_metrics.csv")
    means=docs.groupby("extraction_method").processing_time_seconds.mean()
    fig,ax=plt.subplots(figsize=(7,5)); ax.bar(means.index,means.values,color=[GREEN,TAN])
    _style(ax,"Processing time by extraction method","Seconds per variant")
    _save(fig,charts/"processing_time_by_method.png")

    metrics=json.loads((evaluation_dir/"document_type_metrics.json").read_text())
    fig,ax=plt.subplots(figsize=(5,4)); image=ax.imshow(metrics["confusion_matrix"],cmap="Greens")
    ax.set_xticks([0,1],metrics["labels"]); ax.set_yticks([0,1],metrics["labels"])
    ax.set_xlabel("Predicted"); ax.set_ylabel("Actual"); _style(ax,"Document-type confusion matrix")
    for i,row in enumerate(metrics["confusion_matrix"]):
        for j,value in enumerate(row): ax.text(j,i,value,ha="center",va="center",fontweight="bold")
    _save(fig,charts/"document_type_confusion_matrix.png")

