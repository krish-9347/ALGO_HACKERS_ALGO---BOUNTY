from algopy import (
    # On Algorand, assets are native objects rather than smart contracts
    Asset,
    # Global is used to access global variables from the network
    Global,
    # Txn is used access information about the current transcation
    Txn,
    # By default, all numbers in the AVM are 64-bit unsigned integers
    UInt64,
    # ARC4 defines the Algorand ABI for method calling and type encoding
    arc4,
    # gtxn is used to read transaction within the same atomic group
    gtxn,
    # itxn is used to send transactions from within a smart contract
    itxn,
)


# We want the methods in our contract to follow the ARC4 standard
class TaskBounty(arc4.ARC4Contract):
    # Every asset has a unique ID
    # We want to store the ID for the asset we are selling
    asset_id: UInt64

    # We want to store the price for the asset we are selling
    unitary_price: UInt64

    # We want create_application to be a plublic ABI method
    @arc4.abimethod(
        # There are certain actions that a contract call can do
        # Some examples are UpdateApplication, DeleteApplication, and NoOp
        # NoOp is a call that does nothing special after it is exected
        allow_actions=["NoOp"],
        # Require that this method is only callable when creating the app
        create="require",
    )
    def create_application(
        self,
        # The ID of the asset we're selling
        asset_id: Asset,
        # The initial sale price
        unitary_price: UInt64,
    ) -> None:
        # Save the values we passed in to our method in the contract's state
        self.asset_id = asset_id.id
        self.unitary_price = unitary_price

    @arc4.abimethod
    def set_price(self, unitary_price: UInt64) -> None:
        # We don't want anyone to be able to come in and modify the price
        # You could implement some sort of RBAC,
        # but in this case just making sure the caller is the app creator works
        assert Txn.sender == Global.creator_address

        # Save the new price
        self.unitary_price = unitary_price

    # Before any account can receive an asset, it must opt-in to it
    # This method enables the application to opt-in to the asset
    @arc4.abimethod
    def opt_in_to_asset(
        self,
        # Whenever someone calls this method, they also need to send a payment
        # A payment transaction is a transfer of ALGO
        mbr_pay: gtxn.PaymentTransaction,
    ) -> None:
        # We want to make sure that the application address is not already opted in
        assert not Global.current_application_address.is_opted_in(Asset(self.asset_id))

        # Just like asserting fields in Txn, we can assert fields in the PaymentTxn
        # We can do this only because it is grouped atomically with our app call

        # Just because we made it an argument to the method, there's no gurantee
        # it is being sent to the aplication's address so we need to manually assert
        assert mbr_pay.receiver == Global.current_application_address

        # On Algorand, each account has a minimum balance requirement (MBR)
        # The MBR is locked in the account and cannot be spent (until explicitly unlocked)
        # Every accounts has an MBR of 0.1 ALGO (Global.min_balance)
        # Opting into an asset increases the MBR by 0.1 ALGO (Global.asset_opt_in_min_balance)
        assert mbr_pay.amount == Global.min_balance + Global.asset_opt_in_min_balance

        # Transactions can be sent from a user via signatures
        # They can also be sent programmatically from a smart contract
        # Here we want to issue an opt-in transaction
        # An opt-in transaction is simply transferring 0 of an asset to yourself
        itxn.AssetTransfer(
            xfer_asset=self.asset_id,
            asset_receiver=Global.current_application_address,
            asset_amount=0,
        ).submit()

    @arc4.abimethod
    def buy(
        self,
        # To buy assets, a payment must be sent
        buyer_txn: gtxn.PaymentTransaction,
        # The quantity of assets to buy
        quantity: UInt64,
    ) -> None:
        # We need to verify that the payment is being sent to the application
        # and is enough to cover the cost of the asset
        assert buyer_txn.sender == Txn.sender
        assert buyer_txn.receiver == Global.current_application_address
        assert buyer_txn.amount == self.unitary_price * quantity

        # Once we've verified the payment, we can transfer the asset
        itxn.AssetTransfer(
            xfer_asset=self.asset_id,
            asset_receiver=Txn.sender,
            asset_amount=quantity,
        ).submit()


    arc4.abimethod
    def dispute_task(self) -> None:
        assert self.task_status == UInt64(2), "Task must be submitted to dispute"
        assert Txn.sender == self.task_claimer or Txn.sender == Global.creator_address, "Only claimer or creator can         dispute"
        self.task_status = UInt64(4)  # disputed

    @arc4.abimethod
def get_price(self) -> UInt64:
    return self.unitary_price


class TaskBounty(arc4.ARC4Contract):
    asset_id: UInt64
    unitary_price: UInt64

    task_claimer: abi.StaticBytes[Address]
    task_quantity: UInt64
    task_status: UInt64  # 0 = open, 1 = claimed, 2 = submitted, 3 = completed

    @arc4.abimethod(create="require", allow_actions=["NoOp"])
    def create_application(
        self,
        asset_id: Asset,
        unitary_price: UInt64,
    ) -> None:
        self.asset_id = asset_id.id
        self.unitary_price = unitary_price
        self.task_status = UInt64(0)  # Initial state: open

    @arc4.abimethod
    def claim_task(self, quantity: UInt64) -> None:
        assert self.task_status == UInt64(0), "Task not open"
        self.task_claimer = Txn.sender
        self.task_quantity = quantity
        self.task_status = UInt64(1)  # claimed

    @arc4.abimethod
    def submit_task(self) -> None:
        assert self.task_status == UInt64(1), "Task not in claimed state"
        assert Txn.sender == self.task_claimer, "Only claimer can submit"
        self.task_status = UInt64(2)  # submitted

    @arc4.abimethod
    def approve_task(self) -> None:
        assert self.task_status == UInt64(2), "Task not submitted yet"
        assert Txn.sender == Global.creator_address, "Unauthorized"

        # Send reward
        itxn.AssetTransfer(
            xfer_asset=self.asset_id,
            asset_receiver=self.task_claimer,
            asset_amount=self.task_quantity,
        ).submit()

        self.task_status = UInt64(3)  # completed

    @arc4.abimethod
    def get_task_status(self) -> UInt64:
        return self.task_status


@arc4.abimethod
def set_price(self, unitary_price: UInt64) -> None:
    assert Txn.sender == Global.creator_address, "Only creator can update price"
    self.unitary_price = unitary_price
5)feat: implement DAO voting mechanism to resolve task disputes

@arc4.abimethod
    def dispute_task(self) -> None:
        # Anyone can raise a dispute if the task is submitted
        assert self.task_status == UInt64(2), "Task not submitted"
        self.task_status = UInt64(4)  # disputed
        self.voting_active = True
        self.yes_votes = UInt64(0)
        self.no_votes = UInt64(0)

    @arc4.abimethod
    def vote(self, support: bool) -> None:
        # Voting only allowed during dispute
        assert self.task_status == UInt64(4), "No active dispute"
        assert self.voting_active, "Voting closed"
        
        # For simplicity, allow one vote per sender (no duplicate check here; you'd add this in production)
        if support:
            self.yes_votes += UInt64(1)
        else:
            self.no_votes += UInt64(1)

    @arc4.abimethod
    def finalize_vote(self) -> None:
        # Only creator or DAO can finalize vote
        assert Txn.sender == Global.creator_address, "Unauthorized"
        assert self.task_status == UInt64(4), "No dispute active"
        assert self.voting_active, "Voting already finalized"

        self.voting_active = False

        if self.yes_votes > self.no_votes:
            # Accept task and release reward
            itxn.AssetTransfer(
                xfer_asset=self.asset_id,
                asset_receiver=self.task_claimer,
                asset_amount=self.task_quantity,
            ).submit()
            self.task_status = UInt64(3)  # completed
        else:
            # Reject task, reset to open for reassignment or cancellation
            self.task_status = UInt64(0)  # open
            
@arc4.abimethod
def claim_task(self, quantity: UInt64, escrow_payment: gtxn.PaymentTransaction) -> None:
    # Task must be open
    assert self.task_status == UInt64(0), "Task not open"

    # Escrow payment must be sent by claimer to app address, equal to reward amount
    assert escrow_payment.sender == Txn.sender, "Escrow payment sender mismatch"
    assert escrow_payment.receiver == Global.current_application_address, "Escrow payment must go to app"
    assert escrow_payment.amount == self.unitary_price * quantity, "Incorrect escrow payment amount"

    # Lock the reward in escrow by receiving ALGO payment to app account
    self.task_claimer = Txn.sender
    self.task_quantity = quantity
    self.task_status = UInt64(1)  # claimed


    @arc4.abimethod
def withdraw_assets(self, amount: UInt64) -> None:
    assert Txn.sender == Global.creator_address, "Unauthorized"

    itxn.AssetTransfer(
        xfer_asset=self.asset_id,
        asset_receiver=Global.creator_address,
        asset_amount=amount
    ).submit()
    
deadline: UInt64  # new state variable

@arc4.abimethod
def set_deadline(self, new_deadline: UInt64) -> None:
    assert Txn.sender == Global.creator_address, "Only creator can set deadline"
    self.deadline = new_deadline
    
@arc4.abimethod
def is_task_expired(self) -> bool:
    return Global.latest_timestamp > self.deadline   

@arc4.abimethod
def penalize_claimer(self, penalty_amount: UInt64) -> None:
    assert Txn.sender == Global.creator_address, "Only creator can penalize"
    assert self.task_status == UInt64(2) or self.task_status == UInt64(4), "Only during submission/dispute"

    itxn.Payment(
        receiver=Global.creator_address,
        amount=penalty_amount
    ).submit()

    self.task_status = UInt64(0)  # reopen task
    self.task_claimer = arc4.Address("")
    self.task_quantity = UInt64(0)


@arc4.abimethod
def reassign_task(self) -> None:
    assert self.task_status == UInt64(1), "Task not in claimed state"
    assert Global.latest_timestamp > self.deadline, "Deadline not passed"

    self.task_claimer = arc4.Address("")
    self.task_quantity = UInt64(0)
    self.task_status = UInt64(0)


task_counts: dict[arc4.Address, UInt64]

@arc4.abimethod
def claim_task(self, quantity: UInt64, escrow_payment: gtxn.PaymentTransaction) -> None:
    # ... existing checks
    self.task_counts[Txn.sender] = self.task_counts.get(Txn.sender, UInt64(0)) + UInt64(1)


user_ratings: dict[arc4.Address, abi.DynamicArray[UInt64]]

@arc4.abimethod
def rate_claimer(self, stars: UInt64) -> None:
    assert self.task_status == UInt64(3), "Task must be completed"
    assert Txn.sender == Global.creator_address
    assert stars >= UInt64(1) and stars <= UInt64(5), "Invalid rating"

    self.user_ratings[self.task_claimer].append(stars)

@arc4.abimethod
def auto_reopen(self) -> None:
    assert self.task_status in [UInt64(1), UInt64(2)]
    assert Global.latest_timestamp > self.deadline

    self.task_claimer = arc4.Address("")
    self.task_quantity = UInt64(0)
    self.task_status = UInt64(0)


extension_votes: dict[arc4.Address, bool]
extension_threshold: UInt64

@arc4.abimethod
def vote_extend_deadline(self) -> None:
    assert not self.extension_votes[Txn.sender], "Already voted"
    self.extension_votes[Txn.sender] = True

    vote_count = Global.group_size  # simplistic placeholder
    if vote_count >= self.extension_threshold:
        self.deadline += UInt64(86400)  # Extend by 1 day

user_streaks: dict[arc4.Address, UInt64]

@arc4.abimethod
def on_task_approved(self) -> None:
    assert Txn.sender == Global.creator_address
    self.user_streaks[self.task_claimer] = self.user_streaks.get(self.task_claimer, UInt64(0)) + UInt64(1)

    if self.user_streaks[self.task_claimer] >= UInt64(5):
        itxn.Payment(
            receiver=self.task_claimer,
            amount=Int(100000),  # small bonus
        ).submit()

@arc4.abimethod
def submit_proof_url(self, proof: abi.String) -> None:
    assert self.task_status == UInt64(1), "No task in progress"
    assert Txn.sender == self.task_claimer
    self.proofs[Txn.sender] = proof



@arc4.abimethod
def auto_reopen_if_failed(self) -> None:
    """Automatically reopens a task if deadline has passed and it's not completed."""
    assert self.task_status == UInt64(1), "Task is not in progress"
    assert Global.latest_timestamp > self.deadline, "Deadline not passed yet"

    self.task_status = UInt64(0)  # Back to 'Available'
    self.task_claimer = arc4.Address("")  # Reset claimer
    self.task_quantity = UInt64(0)  # Reset quantity if used

    @arc4.abimethod
def get_algo_balance(self) -> UInt64:
    return Global.current_application_address.balance()

    

    @arc4.abimethod(
        # This method is called when the application is deleted
        allow_actions=["DeleteApplication"]
    )
    def delete_application(self) -> None:
        # Only allow the creator to delete the application
        assert Txn.sender == Global.creator_address

        # Send all the unsold assets to the creator
        itxn.AssetTransfer(
            xfer_asset=self.asset_id,
            asset_receiver=Global.creator_address,
            # The amount is 0, but the asset_close_to field is set
            # This means that ALL assets are being sent to the asset_close_to address
            asset_amount=0,
            # Close the asset to unlock the 0.1 ALGO that was locked in opt_in_to_asset
            asset_close_to=Global.creator_address,
        ).submit()
  
        # Send the remaining balance to the creator
        itxn.Payment(
            receiver=Global.creator_address,
            amount=0,
            # Close the account to get back ALL the ALGO in the account
            close_remainder_to=Global.creator_address,
        ).submit()
