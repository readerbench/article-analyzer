
import csv
import json
import os
import re
from tqdm import tqdm
import numpy as np
from xml.dom.minidom import parse
import xml.dom.minidom
import tensorflow as tf
from transformers import AutoTokenizer, TFT5ForConditionalGeneration, TFLogitsProcessor, TFAutoModelForSeq2SeqLM, AutoModelForCausalLM, BeamSearchScorer, LogitsProcessor, LogitsProcessorList
from cleantext import clean
        
#tf.config.set_visible_devices([], 'GPU')
tokenizer = AutoTokenizer.from_pretrained("google/flan-t5-xl")
model = TFT5ForConditionalGeneration.from_pretrained("google/flan-t5-xl")
    
def compute_loss(labels, logits):
    loss_fn = tf.keras.losses.SparseCategoricalCrossentropy(
        from_logits=True, reduction=tf.keras.losses.Reduction.NONE
    )
    loss = loss_fn(labels, logits)
    return tf.reduce_sum(loss, axis=-1)

def is_study(text, prompt):
    global tokenizer, model
    input_ids = tokenizer(prompt + text, return_tensors="tf").input_ids
    labels = tokenizer(["Yes", "No"], return_tensors="tf").input_ids[:, :-1]

    logits = model(input_ids=input_ids, decoder_input_ids=tf.zeros((1,1), dtype=tf.int32)).logits
    loss = compute_loss(labels, tf.concat([logits, logits], axis=0))
    ratio = float(np.exp(loss[1]-loss[0]))  # P(yes) / P(no)
    return loss[0], loss[1], ratio

class OnlyNumbersProcessor(TFLogitsProcessor):
    
    def __init__(self, tokenizer, vocab_size):
        mask = [False] * vocab_size
        for index in tokenizer.all_special_ids:
            mask[index] = True
        for word, index in tokenizer.vocab.items():
            if word.isdigit():
                mask[index] = True
        self.mask = tf.constant(mask, dtype=tf.bool, shape=(1, len(mask)))
        
    def __call__(self, input_ids: tf.Tensor, scores: tf.Tensor, cur_len: int) -> tf.Tensor:
        # applies eos token masking if the first argument is true
        scores = tf.where(
            self.mask,
            scores,
            float("-inf")
        )
        return scores
    
def get_subjects(text, prompt):
    global tokenizer, model
    encoder_input_ids = tokenizer(prompt + text, return_tensors="tf").input_ids
    logits_processor = OnlyNumbersProcessor(tokenizer, model.config.vocab_size)
    num_beams = 4
    num_returned = 1
    # define decoder start token ids
    input_ids = tf.ones((1, num_beams, 1), dtype=tf.int32)
    input_ids = input_ids * model.config.decoder_start_token_id
    
    # add encoder_outputs to model keyword arguments
    encoder_outputs = model.get_encoder()(encoder_input_ids, return_dict=True)
    encoder_outputs.last_hidden_state = tf.repeat(
         tf.expand_dims(encoder_outputs.last_hidden_state, axis=0), num_beams, axis=1
    )
    model_kwargs = {"encoder_outputs": encoder_outputs}
    
    # running beam search using our custom LogitsProcessor
    generated = model.beam_search(      
        input_ids,
        max_length=4,
        logits_processor=logits_processor,
        return_dict_in_generate=True,
        num_return_sequences=num_returned,
        **model_kwargs
    )
    output = tokenizer.decode(generated.sequences[0], skip_special_tokens=True)
    prob = float(tf.exp(generated.scores[0]))
    return output, prob

def evaluate_with_t5(corpus_file, y_pred_rules, largeN_year):
    prompt1 = "Does this text introduce a new study that includes several participants? The text must include the number of participants"
    ratio = 1.3  
    prompt2 = "How many people were involved in the investigation?"  
    probability = 0.0045  
    
    bad_sections = ["introduction", "references", "conclusions"]

    with open(corpus_file, 'rt') as openfile:  # the json file with the eric dataset
        corpus = json.load(openfile)
    all_articles = corpus['corpus']
    total_largeN_using_rules = 0
    total_largeN_using_T5 = 0
    results = []
    
    ok = 1
    for (article_id, title) in tqdm(y_pred_rules):
        if article_id not in [x[0] for x in results] and ok == 1:
            total_largeN_using_rules += 1
            print("partial results: ")
            print(article_id, flush=True)
            print(total_largeN_using_rules, flush=True)
            print(total_largeN_using_T5, flush=True)
            for article in all_articles:
                if article['title'] == title:  # article was considered langeN by rules method
                    max_n = 0
                    max_n_paragraph = None
                    for section in article["sections"]:
                        heading = section["heading"].lower()
                        heading = re.sub(r'[^\w\s]', '', heading)
                        if heading not in bad_sections:  # first filtering after section name
                            try:
                                for entry in section["text"]:
                                    data = entry["paragraph"]
                                    _, _, rat = is_study(data, prompt1)
                                    out, prob = get_subjects(data, prompt2)
                                    
                                    if rat < ratio:  # second filtering
                                        n = 0
                                    elif prob < probability:  # third filtering
                                        n = 0
                                    else:
                                        n = int(out) if out != "" else 0
                                    if n > max_n:
                                        max_n = n
                                        max_n_paragraph = data
                            except Exception as e:
                                print(e)
                    if max_n >= 1000:
                        results.append((article_id, max_n_paragraph))
                        total_largeN_using_T5 += 1
                    

    with open('final_results_' + str(largeN_year) + '.csv', 'w') as g:
        writer = csv.writer(g)
        for (id, data) in results:
            writer.writerow([id, data])

    print("final results")
    print(total_largeN_using_rules, flush=True)
    print(total_largeN_using_T5, flush=True)
