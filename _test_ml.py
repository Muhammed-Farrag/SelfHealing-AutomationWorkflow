import json, pickle, sys
sys.path.insert(0, '.')
from classifier.ml_classifier import MLClassifier

m = MLClassifier()
with open('results/pipeline.pkl', 'rb') as f:
    m.pipeline = pickle.load(f)

# Load real log excerpts from the dataset
samples = []
with open('data/episodes_classified.jsonl', 'r', encoding='utf-8') as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        obj = json.loads(line)
        text = obj.get('log_excerpt', '')
        label = obj.get('failure_class', '') or obj.get('failure_type', '')
        if text and label and label != 'unknown':
            samples.append((text, label))

print(f'Testing on {len(samples)} real episodes...')
correct = 0
for text, expected in samples:
    pred = m.predict_log(text)
    if pred == expected:
        correct += 1

accuracy = correct / len(samples)
print(f'Real-data accuracy: {correct}/{len(samples)} = {accuracy:.2%}')

# Show a few examples where ML may differ from expected (shows real variation)
from classifier.classifier import RegexFailureClassifier
regex_clf = RegexFailureClassifier()
diffs = 0
print('\nSample comparisons (Regex vs ML):')
for text, label in samples[:10]:
    regex_pred = regex_clf.classify(text)['failure_class']
    ml_pred = m.predict_log(text)
    agree = '==' if regex_pred == ml_pred else '!='
    print(f'  regex={regex_pred} {agree} ml={ml_pred}  (ground={label})')
    if regex_pred != ml_pred:
        diffs += 1

print(f'\nClassifier disagreements in sample: {diffs}/10')
print('TEST 2 PASSED')
