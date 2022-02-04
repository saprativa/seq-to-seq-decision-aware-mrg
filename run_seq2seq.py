#!/usr/bin/env python
# coding=utf-8
# Copyright The HuggingFace Team and The HuggingFace Inc. team. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
Fine-tuning the library models for sequence to sequence.
"""
# You can also adapt this script on your own sequence to sequence task. Pointers for this are left as comments.

import logging
import os
import re
import sys
from dataclasses import dataclass, field
from typing import Optional
from torch.autograd import Variable
os.environ["CUDA_DEVICE_ORDER"]="PCI_BUS_ID"
os.environ['CUDA_VISIBLE_DEVICES']="0"

from torchviz import make_dot

import numpy as np
from datasets import load_dataset, load_metric
import torch
import transformers

sys.path.append('/custom')
# from custom.configuration_bart import BartConfig

# from transformers.models.custom.custom_model import BartForConditionalGeneration,BartEncoderLayer,BartEncoder
# from custom.custom_model import BartEncoderLayer
from tokenizers.implementations import ByteLevelBPETokenizer
from tokenizers.processors import BertProcessing


# from transformers.models.custom.experiment_decsion_at_last_layer_save_5ep import BartForConditionalGeneration,BartEncoderLayer,BartEncoder
# from transformers.models.custom.custom_model_bart_prev_try_2multi_source_with_no_decsion import BartForConditionalGeneration,BartEncoderLayer,BartEncoder
# from transformers.models.custom.custom_model_bart_prev_try_2multi_source_with_decision_at_last import BartForConditionalGeneration,BartEncoderLayer,BartEncoder
from transformers.models.custom.custom_model_bart_multi_decsion_ext_feat_in_decoder import BartForConditionalGeneration,BartEncoderLayer,BartEncoder


# sys.path[-2]='/Data/aizan/amish/EACL/HTMS/trans/transformers/src'
#sftp://aizan@172.16.26.60/Data/aizan/anaconda3/envs/transfomers/lib/python3.6/site-packages/transformers

from transformers import (
    AutoConfig,
    AutoModelForSeq2SeqLM,
    AutoTokenizer,
    DataCollatorForSeq2Seq,
    HfArgumentParser,
    MBartTokenizer,
    Seq2SeqTrainer,
    Seq2SeqTrainingArguments,
    default_data_collator,
    set_seed,
)
from transformers.trainer_utils import get_last_checkpoint, is_main_process


logger = logging.getLogger(__name__)


@dataclass
class ModelArguments:
    """
    Arguments pertaining to which model/config/tokenizer we are going to fine-tune from.
    """

    model_name_or_path: str = field(
        metadata={"help": "Path to pretrained model or model identifier from huggingface.co/models"}
    )
    config_name: Optional[str] = field(
        default=None, metadata={"help": "Pretrained config name or path if not the same as model_name"}
    )
    tokenizer_name: Optional[str] = field(
        default=None, metadata={"help": "Pretrained tokenizer name or path if not the same as model_name"}
    )
    cache_dir: Optional[str] = field(
        default=None,
        metadata={"help": "Where to store the pretrained models downloaded from huggingface.co"},
    )
    use_fast_tokenizer: bool = field(
        default=True,
        metadata={"help": "Whether to use one of the fast tokenizer (backed by the tokenizers library) or not."},
    )
    model_revision: str = field(
        default="main",
        metadata={"help": "The specific model version to use (can be a branch name, tag name or commit id)."},
    )
    use_auth_token: bool = field(
        default=False,
        metadata={
            "help": "Will use the token generated when running `transformers-cli login` (necessary to use this script "
            "with private models)."
        },
    )


@dataclass
class DataTrainingArguments:
    """
    Arguments pertaining to what data we are going to input our model for training and eval.
    """

    task: str = field(
        default="summarization",
        metadata={
            "help": "The name of the task, should be summarization (or summarization_{dataset} for evaluating "
            "pegasus) or translation (or translation_{xx}_to_{yy})."
        },
    )
    dataset_name: Optional[str] = field(
        default=None, metadata={"help": "The name of the dataset to use (via the datasets library)."}
    )
    dataset_config_name: Optional[str] = field(
        default=None, metadata={"help": "The configuration name of the dataset to use (via the datasets library)."}
    )
    text_column1: Optional[str] = field(
        default='review1',
        metadata={"help": "The name of the column in the datasets containing the full texts (for summarization)."},
    )
    text_column2: Optional[str] = field(
        default='review2',
        metadata={"help": "The name of the column in the datasets containing the full texts (for summarization)."},
    )
    text_column3: Optional[str] = field(
        default='review3',
        metadata={"help": "The name of the column in the datasets containing the full texts (for summarization)."},
    )
    summary_column: Optional[str] = field(
        default=None,
        metadata={"help": "The name of the column in the datasets containing the summaries (for summarization)."},
    )
    decision_label: Optional[str] = field(
        default=None,
        metadata={"help": "The name of the column in the datasets containing the summaries (for summarization)."},
    )
    feat_index: Optional[str] = field(
        default=None,
        metadata={"help": "The name of the column in the datasets containing the summaries (for summarization)."},
    )
    # indexs: Optional[str] = field(
    #     default='index',
    #     metadata={"help": "The name of the column in the datasets containing the summaries (for summarization)."},
    # )
    train_file: Optional[str] = field(default=None, metadata={"help": "The input training data file (a text file)."})
    validation_file: Optional[str] = field(
        default=None,
        metadata={"help": "An optional input evaluation data file to evaluate the perplexity on (a text file)."},
    )
    overwrite_cache: bool = field(
        default=False, metadata={"help": "Overwrite the cached training and evaluation sets"}
    )
    preprocessing_num_workers: Optional[int] = field(
        default=None,
        metadata={"help": "The number of processes to use for the preprocessing."},
    )
    max_source_length: Optional[int] = field(
        default=1024,
        metadata={
            "help": "The maximum total input sequence length after tokenization. Sequences longer "
            "than this will be truncated, sequences shorter will be padded."
        },
    )
    max_target_length: Optional[int] = field(
        default=128,
        metadata={
            "help": "The maximum total sequence length for target text after tokenization. Sequences longer "
            "than this will be truncated, sequences shorter will be padded."
        },
    )
    val_max_target_length: Optional[int] = field(
        default=None,
        metadata={
            "help": "The maximum total sequence length for validation target text after tokenization. Sequences longer "
            "than this will be truncated, sequences shorter will be padded. Will default to `max_target_length`."
            "This argument is also used to override the ``max_length`` param of ``model.generate``, which is used "
            "during ``evaluate`` and ``predict``."
        },
    )
    pad_to_max_length: bool = field(
        default=False,
        metadata={
            "help": "Whether to pad all samples to model maximum sentence length. "
            "If False, will pad the samples dynamically when batching to the maximum length in the batch. More "
            "efficient on GPU but very bad for TPU."
        },
    )
    max_train_samples: Optional[int] = field(
        default=None,
        metadata={
            "help": "For debugging purposes or quicker training, truncate the number of training examples to this "
            "value if set."
        },
    )
    max_val_samples: Optional[int] = field(
        default=None,
        metadata={
            "help": "For debugging purposes or quicker training, truncate the number of validation examples to this "
            "value if set."
        },
    )
    max_test_samples: Optional[int] = field(
        default=None,
        metadata={
            "help": "For debugging purposes or quicker training, truncate the number of test examples to this "
            "value if set."
        },
    )
    source_lang: Optional[str] = field(default=None, metadata={"help": "Source language id for translation."})
    target_lang: Optional[str] = field(default=None, metadata={"help": "Target language id for translation."})
    num_beams: Optional[int] = field(
        default=None,
        metadata={
            "help": "Number of beams to use for evaluation. This argument will be passed to ``model.generate``, "
            "which is used during ``evaluate`` and ``predict``."
        },
    )
    ignore_pad_token_for_loss: bool = field(
        default=True,
        metadata={
            "help": "Whether to ignore the tokens corresponding to padded labels in the loss computation or not."
        },
    )
    source_prefix: Optional[str] = field(
        default=None, metadata={"help": "A prefix to add before every source text (useful for T5 models)."}
    )

    def __post_init__(self):
        if self.dataset_name is None and self.train_file is None and self.validation_file is None:
            raise ValueError("Need either a dataset name or a training/validation file.")
        else:
            if self.train_file is not None:
                extension = self.train_file.split(".")[-1]
                assert extension in ["csv", "json"], "`train_file` should be a csv or a json file."
            if self.validation_file is not None:
                extension = self.validation_file.split(".")[-1]
                assert extension in ["csv", "json"], "`validation_file` should be a csv or a json file."
        if not self.task.startswith("summarization") and not self.task.startswith("translation"):
            raise ValueError(
                "`task` should be summarization, summarization_{dataset}, translation or translation_{xx}_to_{yy}."
            )
        if self.val_max_target_length is None:
            self.val_max_target_length = self.max_target_length


summarization_name_mapping = {
    "amazon_reviews_multi": ("review_body", "review_title"),
    "big_patent": ("description", "abstract"),
    "cnn_dailymail": ("article", "highlights"),
    "orange_sum": ("text", "summary"),
    "pn_summary": ("article", "summary"),
    "psc": ("extract_text", "summary_text"),
    "samsum": ("dialogue", "summary"),
    "thaisum": ("body", "summary"),
    "xglue": ("news_body", "news_title"),
    "xsum": ("document", "summary"),
    "wiki_summary": ("article", "highlights"),
}


def main():
    # See all possible arguments in src/transformers/training_args.py
    # or by passing the --help flag to this script.
    # We now keep distinct sets of args, for a cleaner separation of concerns.

    parser = HfArgumentParser((ModelArguments, DataTrainingArguments, Seq2SeqTrainingArguments))
    if len(sys.argv) == 2 and sys.argv[1].endswith(".json"):
        # If we pass only one argument to the script and it's the path to a json file,
        # let's parse it to get our arguments.
        model_args, data_args, training_args = parser.parse_json_file(json_file=os.path.abspath(sys.argv[1]))
    else:
        model_args, data_args, training_args = parser.parse_args_into_dataclasses()

    # Detecting last checkpoint.
    last_checkpoint = None
    if os.path.isdir(training_args.output_dir) and training_args.do_train and not training_args.overwrite_output_dir:
        last_checkpoint = get_last_checkpoint(training_args.output_dir)
        if last_checkpoint is None and len(os.listdir(training_args.output_dir)) > 0:
            raise ValueError(
                f"Output directory ({training_args.output_dir}) already exists and is not empty. "
                "Use --overwrite_output_dir to overcome."
            )
        elif last_checkpoint is not None:
            logger.info(
                f"Checkpoint detected, resuming training at {last_checkpoint}. To avoid this behavior, change "
                "the `--output_dir` or add `--overwrite_output_dir` to train from scratch."
            )

    # Setup logging
    logging.basicConfig(
        format="%(asctime)s - %(levelname)s - %(name)s -   %(message)s",
        datefmt="%m/%d/%Y %H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    logger.setLevel(logging.INFO if is_main_process(training_args.local_rank) else logging.WARN)

    # Log on each process the small summary:
    # training_args.device=torch.cuda.set_device(torch.device('cuda:5'))
    # print(training_args.device,'_______________________________________________--')
    logger.warning(
        f"Process rank: {training_args.local_rank}, device: {training_args.device}, n_gpu: {training_args.n_gpu}"
        + f"distributed training: {bool(training_args.local_rank != -1)}, 16-bits training: {training_args.fp16}"
    )
    # Set the verbosity to info of the Transformers logger (on main process only):
    if is_main_process(training_args.local_rank):
        transformers.utils.logging.set_verbosity_info()
    logger.info("Training/evaluation parameters %s", training_args)

    # Set seed before initializing model.
    set_seed(training_args.seed)

    # Get the datasets: you can either provide your own CSV/JSON training and evaluation files (see below)
    # or just provide the name of one of the public datasets available on the hub at https://huggingface.co/datasets/
    # (the dataset will be downloaded automatically from the datasets Hub).
    #
    # For CSV/JSON files in the summarization task, this script will use the first column for the full texts and the
    # second column for the summaries (unless you specify column names for this with the `text_column` and
    # `summary_column` arguments).
    # For translation, only JSON files are supported, with one field named "translation" containing two keys for the
    # source and target languages (unless you adapt what follows).
    #
    # In distributed training, the load_dataset function guarantee that only one local process can concurrently
    # download the dataset.
    if data_args.dataset_name is not None:
        # Downloading and loading a dataset from the hub.
        datasets = load_dataset(data_args.dataset_name, data_args.dataset_config_name)
    else:
        data_files = {}
        if data_args.train_file is not None:
            data_files["test"] = data_args.train_file
            extension = data_args.train_file.split(".")[-1]
        if data_args.validation_file is not None:
            data_files["validation"] = data_args.validation_file
            extension = data_args.validation_file.split(".")[-1]
        datasets = load_dataset(extension, data_files=data_files)
    # See more about loading any type of standard or custom dataset (from files, python dict, pandas DataFrame, etc) at
    # https://huggingface.co/docs/datasets/loading_datasets.html.

    # Load pretrained model and tokenizer
    #
    # Distributed training:
    # The .from_pretrained methods guarantee that only one local process can concurrently
    # download model & vocab.


    config = AutoConfig.from_pretrained(
        model_args.config_name if model_args.config_name else model_args.model_name_or_path,
        cache_dir=model_args.cache_dir,
        revision=model_args.model_revision,
        use_auth_token=True if model_args.use_auth_token else None,
    )
    
    tokenizer = AutoTokenizer.from_pretrained(
        model_args.tokenizer_name if model_args.tokenizer_name else model_args.model_name_or_path,
        cache_dir=model_args.cache_dir,
        use_fast=model_args.use_fast_tokenizer,
        revision=model_args.model_revision,
        use_auth_token=True if model_args.use_auth_token else None,
    )


    # model = AutoModelForSeq2SeqLM.from_config(
    #     # model_args.model_name_or_path,
    #     # from_tf=bool(".ckpt" in model_args.model_name_or_path),
    #     config=config,
    #     # cache_dir=model_args.cache_dir,
    #     # revision=model_args.model_revision,
    #     # use_auth_token=True if model_args.use_auth_token else None,
    # )


    # config=AutoConfig.from_pretrained(model_args.model_name_or_path+'/config.json')
    # tokenizer=AutoTokenizer.from_pretrained(model_args.model_name_or_path+'/',max_len=512)
    # print(tokenizer,'tokenizer')

    model=BartForConditionalGeneration(config=config)
    model.load_state_dict(torch.load(model_args.model_name_or_path+'/pytorch_model.bin'))
    print('model loaded')
    print(model)
    pytorch_total_params = sum(p.numel() for p in model.parameters())
    print(pytorch_total_params,'pytorch_total_params')
    pytorch_total_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(pytorch_total_params)
    # x = torch.zeros(1, 1024, 1024, dtype=torch.float, requires_grad=False).to(torch.int64)
    # y=torch.zeros(1,1, 1024, 1024, dtype=torch.float, requires_grad=False).to(torch.int64)
    # print(x.shape,'x_shape')
    # print(y.shape,'y_sahpe')
    # dummy_inputs=model.dummy_inputs()
    # print(dummy_inputs)
    # out = model(attention_mask=Variable(dummy_inputs['attention_mask']),input_ids=Variable(dummy_inputs['input_ids']))
    # print(type(out[0]))
    # make_dot(out)

    # Set decoder_start_token_id
    if model.config.decoder_start_token_id is None and isinstance(tokenizer, MBartTokenizer):
        model.config.decoder_start_token_id = tokenizer.lang_code_to_id[data_args.target_lang]
    if model.config.decoder_start_token_id is None:
        raise ValueError("Make sure that `config.decoder_start_token_id` is correctly defined")

    # Get the default prefix if None is passed.
    if data_args.source_prefix is None:
        task_specific_params = model.config.task_specific_params
        if task_specific_params is not None:
            prefix = task_specific_params.get("prefix", "")
        else:
            prefix = ""
    else:
        prefix = data_args.source_prefix

    # Preprocessing the datasets.
    # We need to tokenize inputs and targets.
    if training_args.do_train:
        column_names = datasets["train"].column_names
    elif training_args.do_eval:
        column_names = datasets["validation"].column_names
    elif training_args.do_predict:
        column_names = datasets["test"].column_names
    else:
        logger.info("There is nothing to do. Please pass `do_train`, `do_eval` and/or `do_predict`.")
        return

    # For translation we set the codes of our source and target languages (only useful for mBART, the others will
    # ignore those attributes).
    if data_args.task.startswith("translation"):
        if data_args.source_lang is not None:
            tokenizer.src_lang = data_args.source_lang
        if data_args.target_lang is not None:
            tokenizer.tgt_lang = data_args.target_lang

    # To serialize preprocess_function below, each of those four variables needs to be defined (even if we won't use
    # them all).
    source_lang, target_lang, text_column, summary_column = None, None, None, None

    if data_args.task.startswith("summarization"):
        # Get the column names for input/target.
        dataset_columns = summarization_name_mapping.get(data_args.dataset_name, None)
        if data_args.text_column1 is None:
            text_column = dataset_columns[0] if dataset_columns is not None else column_names[0]
        else:
            text_column1 = data_args.text_column1
            text_column2 = data_args.text_column2
            text_column3 = data_args.text_column3
        if data_args.summary_column is None:
            summary_column = dataset_columns[1] if dataset_columns is not None else column_names[1]
        else:
            summary_column = data_args.summary_column
        if data_args.decision_label is not None:
            decision_label=data_args.decision_label
# indexs=data_args.indexs
        if data_args.feat_index is not None:
            feat_index=data_args.feat_index
    else:
        # Get the language codes for input/target.
        lang_search = re.match("translation_([a-z]+)_to_([a-z]+)", data_args.task)
        if data_args.source_lang is not None:
            source_lang = data_args.source_lang.split("_")[0]
        else:
            assert (
                lang_search is not None
            ), "Provide a source language via --source_lang or rename your task 'translation_xx_to_yy'."
            source_lang = lang_search.groups()[0]

        if data_args.target_lang is not None:
            target_lang = data_args.target_lang.split("_")[0]
        else:
            assert (
                lang_search is not None
            ), "Provide a target language via --target_lang or rename your task 'translation_xx_to_yy'."
            target_lang = lang_search.groups()[1]

    # Temporarily set max_target_length for training.
    max_target_length = data_args.max_target_length
    padding = "max_length" if data_args.pad_to_max_length else False

    if training_args.label_smoothing_factor > 0 and not hasattr(model, "prepare_decoder_input_ids_from_labels"):
        logger.warn(
            "label_smoothing is enabled but the `prepare_decoder_input_ids_from_labels` method is not defined for"
            f"`{model.__class__.__name__}`. This will lead to loss being calculated twice and will take up more memory"
        )
    def preprocess_function(examples):
        if data_args.task.startswith("translation"):
            inputs = [ex[source_lang] for ex in examples["translation"]]
            targets = [ex[target_lang] for ex in examples["translation"]]
        else:
            inputs1 = examples[text_column1]
            inputs2 = examples[text_column2]
            inputs3 = examples[text_column3]
            targets = examples[summary_column]
        inputs1 = [prefix + inp if inp!=None else  '' for inp in inputs1  ]
        inputs2 = [prefix + inp if inp!=None else  '' for inp in inputs2  ]
        inputs3 = [prefix + inp if inp!=None else  '' for inp in inputs3  ]
        model_inputs2 = tokenizer(inputs2, max_length=data_args.max_source_length, padding=padding, truncation=True)
        model_inputs3 =  tokenizer(inputs3, max_length=data_args.max_source_length, padding=padding, truncation=True)
        model_inputs1 = tokenizer(inputs1, max_length=data_args.max_source_length, padding=padding, truncation=True)

        # print(model_inputs)
        # sys.exit(0)
        # model_inputs =  tokenizer(inputs3, max_length=data_args.max_source_length, padding=padding, truncation=True)
        # model_inputs = tokenizer(inputs1, max_length=data_args.max_source_length, padding=padding, truncation=True)
        # model_inputs = tokenizer(inputs1, max_length=data_args.max_source_length, padding=padding, truncation=True)
        model_inputs={}
        model_inputs["input_ids"]=model_inputs1['input_ids']#{'input_ids1':model_inputs1["input_ids"],'input_ids2':model_inputs2['input_ids'],'input_ids':model_inputs3}
        model_inputs["input_ids2"] = model_inputs2["input_ids"]
        model_inputs["input_ids3"] = model_inputs3["input_ids"]
        model_inputs["attention_mask2"] =model_inputs2["attention_mask"]
        model_inputs["attention_mask3"] =model_inputs3["attention_mask"]
        model_inputs["attention_mask"] =model_inputs1["attention_mask"]

        # Setup the tokenizer for targets
        with tokenizer.as_target_tokenizer():
            labels = tokenizer(targets, max_length=max_target_length, padding=padding, truncation=True)

        # If we are padding here, replace all tokenizer.pad_token_id in the labels by -100 when we want to ignore
        # padding in the loss.
        if padding == "max_length" and data_args.ignore_pad_token_for_loss:
            labels["input_ids"] = [
                [(l if l != tokenizer.pad_token_id else -100) for l in label] for label in labels["input_ids"]
            ]

        model_inputs["labels"] = labels["input_ids"]
        model_inputs["decision_label"]=examples[decision_label]
        # model_inputs['indexs']=examples[indexs]
        model_inputs['feat_index']=examples[feat_index]
        return model_inputs

    if training_args.do_train:
        train_dataset = datasets["train"]
        if data_args.max_train_samples is not None:
            train_dataset = train_dataset.select(range(data_args.max_train_samples))
        train_dataset = train_dataset.map(
            preprocess_function,
            batched=True,
            num_proc=data_args.preprocessing_num_workers,
            remove_columns=column_names,
            load_from_cache_file=not data_args.overwrite_cache,
        )


    #change this for length
    data_args.val_max_target_length=600

    if training_args.do_eval:
        max_target_length = data_args.val_max_target_length
        eval_dataset = datasets["validation"]
        if data_args.max_val_samples is not None:
            eval_dataset = eval_dataset.select(range(data_args.max_val_samples))
        eval_dataset = eval_dataset.map(
            preprocess_function,
            batched=True,
            num_proc=data_args.preprocessing_num_workers,
            remove_columns=column_names,
            load_from_cache_file=not data_args.overwrite_cache,
        )

    if training_args.do_predict:
        max_target_length = data_args.val_max_target_length
        test_dataset = datasets["test"]
        if data_args.max_test_samples is not None:
            test_dataset = test_dataset.select(range(data_args.max_test_samples))
        test_dataset = test_dataset.map(
            preprocess_function,
            batched=True,
            num_proc=data_args.preprocessing_num_workers,
            remove_columns=column_names,
            load_from_cache_file=not data_args.overwrite_cache,
        )

    # Data collator
    label_pad_token_id = -100 if data_args.ignore_pad_token_for_loss else tokenizer.pad_token_id
    if data_args.pad_to_max_length:
        data_collator = default_data_collator
    else:
        data_collator = DataCollatorForSeq2Seq(
            tokenizer,
            model=model,
            label_pad_token_id=label_pad_token_id,
            pad_to_multiple_of=8 if training_args.fp16 else None,
        )

    # Metric
    metric_name = "rouge" if data_args.task.startswith("summarization") else "sacrebleu"
    metric = load_metric(metric_name)

    def compute_metrics(eval_preds):
        preds, labels = eval_preds
        if isinstance(preds, tuple):
            preds = preds[0]
        decoded_preds = tokenizer.batch_decode(preds, skip_special_tokens=True)
        if data_args.ignore_pad_token_for_loss:
            # Replace -100 in the labels as we can't decode them.
            labels = np.where(labels != -100, labels, tokenizer.pad_token_id)
        decoded_labels = tokenizer.batch_decode(labels, skip_special_tokens=True)

        # Some simple post-processing
        decoded_preds = [pred.strip() for pred in decoded_preds]
        decoded_labels = [label.strip() for label in decoded_labels]
        if metric_name == "sacrebleu":
            decoded_labels = [[label] for label in decoded_labels]

        result = metric.compute(predictions=decoded_preds, references=decoded_labels)

        # Extract a few results from ROUGE
        if metric_name == "rouge":
            result = {key: value.mid.fmeasure * 100 for key, value in result.items()}
        else:
            result = {"bleu": result["score"]}

        prediction_lens = [np.count_nonzero(pred != tokenizer.pad_token_id) for pred in preds]
        result["gen_len"] = np.mean(prediction_lens)

        return result

    # Initialize our Trainer
    trainer = Seq2SeqTrainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset if training_args.do_train else None,
        eval_dataset=eval_dataset if training_args.do_eval else None,
        tokenizer=tokenizer,
        data_collator=data_collator,
        compute_metrics=compute_metrics if training_args.predict_with_generate else None,
    )
    # print(type(trainer),'trainer')

    # Training
    if training_args.do_train:
        if last_checkpoint is not None:
            checkpoint = last_checkpoint
        elif os.path.isdir(model_args.model_name_or_path):
            checkpoint = model_args.model_name_or_path
        else:
            checkpoint = None
        checkpoint=None
        train_result = trainer.train(resume_from_checkpoint=checkpoint)
        trainer.save_model()  # Saves the tokenizer too for easy upload

        output_train_file = os.path.join(training_args.output_dir, "train_results.txt")
        if trainer.is_world_process_zero():
            with open(output_train_file, "w") as writer:
                logger.info("***** Train results *****")
                for key, value in sorted(train_result.metrics.items()):
                    logger.info(f"  {key} = {value}")
                    writer.write(f"{key} = {value}\n")

            # Need to save the state, since Trainer.save_model saves only the tokenizer with the model
            trainer.state.save_to_json(os.path.join(training_args.output_dir, "trainer_state.json"))

    # Evaluation
    results = {}
    if training_args.do_eval:
        logger.info("*** Evaluate ***")

        results = trainer.evaluate(max_length=data_args.val_max_target_length, num_beams=data_args.num_beams)

        output_eval_file = os.path.join(training_args.output_dir, "eval_results_seq2seq.txt")
        if trainer.is_world_process_zero():
            with open(output_eval_file, "w") as writer:
                logger.info("***** Eval results *****")
                for key, value in sorted(results.items()):
                    logger.info(f"  {key} = {value}")
                    writer.write(f"{key} = {value}\n")

    if training_args.do_predict:
        logger.info("*** Test ***")

        test_results = trainer.predict(
            test_dataset,
            metric_key_prefix="test",
            max_length=data_args.val_max_target_length,
            num_beams=data_args.num_beams,
        )
        test_metrics = test_results.metrics

        output_test_result_file = os.path.join(training_args.output_dir, "test_results_seq2seq.txt")
        if trainer.is_world_process_zero():
            with open(output_test_result_file, "w") as writer:
                logger.info("***** Test results *****")
                for key, value in sorted(test_metrics.items()):
                    logger.info(f"  {key} = {value}")
                    writer.write(f"{key} = {value}\n")

            if training_args.predict_with_generate:
                test_preds = tokenizer.batch_decode(
                    test_results.predictions, skip_special_tokens=True, clean_up_tokenization_spaces=True
                )
                print(len(test_preds),'length of istances prediction')
                test_preds = [pred.strip() for pred in test_preds]
                output_test_preds_file = os.path.join(training_args.output_dir, "test_preds_seq2seq.txt")
                with open(output_test_preds_file, "w") as writer:
                    writer.write("\n".join(test_preds))

    return results


def _mp_fn(index):
    # For xla_spawn (TPUs)
    main()


if __name__ == "__main__":
    main()


#python examples/seq2seq/run_seq2seq.py --model_name_or_path ./tst-summarization --do_train False --do_eval True --task summarization --train_file path_to_csv_or_jsonlines_file.csv --validation_file path_to_csv_or_jsonlines_file.csv --output_dir albert --overwrite_output_dir --per_device_train_batch_size=1 --per_device_eval_batch_size=1 --predict_with_generate --text_column review --summary_column summary --do_predict True