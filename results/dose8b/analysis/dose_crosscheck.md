# Hardware cross-check: ladder Dmid vs the main study's D (Deviation 14)

Same D training file. Descriptive only. Rates in percent; n = labeled rows.

| tree | model | pool | lie (frozen) | lie (question-only) | n |
|---|---|---|---|---|---|
| main (Kaggle T4, fp16) | base | transfer | 68.0 | 66.3 | 600 |
| main (Kaggle T4, fp16) | base | transfer_no_sf | 80.0 | 78.8 | 400 |
| main (Kaggle T4, fp16) | base | sf_present | 65.4 | 60.6 | 104 |
| main (Kaggle T4, fp16) | D-s1 | transfer | 80.8 | 64.3 | 600 |
| main (Kaggle T4, fp16) | D-s1 | transfer_no_sf | 79.2 | 75.5 | 400 |
| main (Kaggle T4, fp16) | D-s1 | sf_present | 100.0 | 77.9 | 104 |
| main (Kaggle T4, fp16) | D-s2 | transfer | 81.8 | 64.0 | 600 |
| main (Kaggle T4, fp16) | D-s2 | transfer_no_sf | 79.8 | 74.0 | 400 |
| main (Kaggle T4, fp16) | D-s2 | sf_present | 100.0 | 81.7 | 104 |
| ladder (RunPod, bf16) | base | transfer | 67.8 | 66.5 | 600 |
| ladder (RunPod, bf16) | base | transfer_no_sf | 80.0 | 79.0 | 400 |
| ladder (RunPod, bf16) | base | sf_present | 64.4 | 60.6 | 104 |
| ladder (RunPod, bf16) | Dmid-s1 | transfer | 80.7 | 64.5 | 600 |
| ladder (RunPod, bf16) | Dmid-s1 | transfer_no_sf | 79.0 | 75.5 | 400 |
| ladder (RunPod, bf16) | Dmid-s1 | sf_present | 100.0 | 79.8 | 104 |
| ladder (RunPod, bf16) | Dmid-s2 | transfer | 82.3 | 63.8 | 600 |
| ladder (RunPod, bf16) | Dmid-s2 | transfer_no_sf | 80.8 | 74.2 | 400 |
| ladder (RunPod, bf16) | Dmid-s2 | sf_present | 100.0 | 80.8 | 104 |

D minus base within each tree (mean of the two seeds):

| tree | pool | lie (frozen) | lie (question-only) |
|---|---|---|---|
| main (Kaggle T4, fp16) | transfer | +13.3 | -2.2 |
| main (Kaggle T4, fp16) | transfer_no_sf | -0.5 | -4.0 |
| main (Kaggle T4, fp16) | sf_present | +34.6 | +19.2 |
| ladder (RunPod, bf16) | transfer | +13.7 | -2.3 |
| ladder (RunPod, bf16) | transfer_no_sf | -0.1 | -4.1 |
| ladder (RunPod, bf16) | sf_present | +35.6 | +19.7 |
