import os
from ai_brain import TradeBrain

def force_train():
    print("🧠 Initializing AI Brain Training...")
    
    # 1. Purani sabhi files hatao (Fresh Training ke liye zaroori hai)
    old_files = [
        "brain_xgboost.pkl", 
        "brain_lightgbm.pkl", 
        "brain_lstm.keras", 
        "brain_scaler.pkl"
    ]
    
    deleted_any = False
    for file in old_files:
        if os.path.exists(file):
            os.remove(file)
            print(f"🗑️ Deleted old file: {file}")
            deleted_any = True
            
    if not deleted_any:
        print("✨ No old models found. Starting fresh!")

    # 2. Brain Object banao
    brain = TradeBrain()
    
    # 3. Training Start karo
    print("🏋️ Starting Training Process (This may take a few minutes)...")
    brain.train_brain()
    
    # 4. Check karo main files bani ya nahi
    if os.path.exists("brain_xgboost.pkl") and os.path.exists("brain_scaler.pkl"):
        size_xgb = os.path.getsize("brain_xgboost.pkl") / 1024 # KB me
        size_scaler = os.path.getsize("brain_scaler.pkl") / 1024 
        print(f"\n✅ SUCCESS: All Brain Models & Scaler Created Successfully!")
        print(f"📊 XGBoost Size: {size_xgb:.2f} KB | Scaler Size: {size_scaler:.2f} KB")
        print("🚀 Now you can safely run 'run.py' and dominate the market!")
    else:
        print("\n❌ FAILURE: Brain files not created. Check Database for sufficient 5m data.")

if __name__ == "__main__":
    force_train()